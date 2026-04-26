import { ChangeDetectorRef, Component, ViewChild, ElementRef } from '@angular/core';
import { ChatService } from './chat.service';
import { marked } from 'marked';

interface ChatMessage {
  role: 'user' | 'bot';
  content: string;
  renderedContent?: string;
  timestamp: string;
}

interface ChatPlot {
  index: number;
  title: string;
  imageUrl: string;
  available: boolean;
}

interface ChatSession {
  id: number;
  name: string;
  uploadedFileName?: string;
  backendChatId?: string; // ID vom Backend (chat_1, chat_2, etc.)
  overview?: string;
  summary?: string;
  plots: ChatPlot[];
  messages: ChatMessage[];
  createdAt: string;
}

@Component({
  selector: 'app-root',
  standalone: false,
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css'],
})
export class AppComponent {
  draftMessage = '';
  selectedChat: ChatSession | null = null;
  chats: ChatSession[] = [];
  nextChatId = 1;
  tempUploadedFile: File | null = null; // Temporäre CSV-Datei
  isLoading = false; // Für Ladezustand

  @ViewChild('chatWindow', { static: false }) chatWindow!: ElementRef;

  constructor(
    private chatService: ChatService,
    private changeDetectorRef: ChangeDetectorRef
  ) {
    marked.setOptions({
      gfm: true,
      breaks: true,
    });

    // Automatisch ersten Chat erstellen
    this.createNewChat();
  }

  get overviewText(): string {
    if (!this.selectedChat) {
      return 'Es wurde noch keine CSV Datei hochgeladen.';
    }
    return this.selectedChat.overview
      ?? (this.selectedChat.uploadedFileName
        ? `Aktuelle CSV: ${this.selectedChat.uploadedFileName}`
        : 'Noch keine CSV für diesen Chat ausgewählt.');
  }

  get summaryText(): string {
    if (!this.selectedChat) {
      return 'Hier wird spaeter die Zusammenfassung fuer den ausgewaehlten Chat angezeigt.';
    }

    return this.selectedChat.summary
      ?? 'Sobald das Backend strukturierte Daten liefert, erscheint hier die feste Zusammenfassung des Chats.';
  }

  get selectedPlots(): ChatPlot[] {
    return this.selectedChat?.plots ?? [];
  }

  get canSendMessage(): boolean {
    if (!this.selectedChat) return false;

    // Erste Nachricht: Muss CSV haben
    if (this.selectedChat.messages.length === 0) {
      return !!this.tempUploadedFile;
    }

    // Nach CSV-Upload: Immer senden möglich (Text oder Text+CSV)
    return true;
  }

  get isCsvUploaded(): boolean {
    return !!this.tempUploadedFile;
  }

  get hasCsvInChat(): boolean {
    return !!this.selectedChat?.uploadedFileName;
  }

  createNewChat(): void {
    const newChat: ChatSession = {
      id: this.nextChatId++,
      name: `Chat ${this.nextChatId - 1}`,
      uploadedFileName: undefined,
      overview: undefined,
      summary: undefined,
      plots: [],
      messages: [],
      createdAt: new Date().toLocaleString('de-DE', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      }),
    };
    this.chats = [newChat, ...this.chats];
    this.selectedChat = newChat;
    this.tempUploadedFile = null; // Temporäre Datei zurücksetzen
    this.draftMessage = '';
  }

  selectChat(chat: ChatSession): void {
    this.selectedChat = chat;
    this.tempUploadedFile = null; // Temporäre Datei zurücksetzen beim Chat-Wechsel
    this.draftMessage = '';
  }

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file || !this.selectedChat) {
      return;
    }

    // Temporär speichern (noch nicht in Chat überführen)
    this.tempUploadedFile = file;

    // Chat-Namen setzen, wenn noch nicht geschehen
    if (!this.selectedChat.uploadedFileName) {
      this.selectedChat.name = file.name.replace('.csv', '');
    }

    input.value = '';
  }

  removeCsv(): void {
    this.tempUploadedFile = null;
  }

  sendMessage(): void {
    if (!this.selectedChat || !this.canSendMessage || this.isLoading) {
      return;
    }

    const currentChat = this.selectedChat;
    const message = this.draftMessage.trim();
    const uploadedFile = this.tempUploadedFile;
    const hasCsv = !!uploadedFile;
    const hasText = !!message;

    if (!hasCsv && !hasText) {
      return;
    }

    this.isLoading = true;

    // User-Nachricht im Chat anzeigen
    let userContent = '';
    if (hasCsv && hasText) {
      userContent = `CSV: ${uploadedFile!.name}\n${message}`;
    } else if (hasCsv) {
      userContent = `CSV: ${uploadedFile!.name}`;
    } else {
      userContent = message;
    }

    currentChat.messages.push({
      role: 'user',
      content: userContent,
      renderedContent: this.escapeHtml(userContent),
      timestamp: this.timeStamp(),
    });

    this.scrollToBottom();

    // Textfeld sofort leeren
    this.draftMessage = '';

    // API-Call machen
    if (hasCsv && uploadedFile) {
      // Direkt sperren, damit im aktiven Chat keine zweite CSV ausgewaehlt werden kann.
      currentChat.uploadedFileName = uploadedFile.name;

      this.chatService.uploadCsv(uploadedFile).subscribe({
        next: (uploadResponse) => {
          currentChat.backendChatId = uploadResponse.chat_id;
          this.tempUploadedFile = null;

          // 2. Sofort die eigentliche Nachricht hinterher (mit chat_id)
          this.callChatApi(message, currentChat);
        },
        error: (error) => {
          this.handleApiError(error, currentChat);
          this.isLoading = false;
        }
      });
    } else if (currentChat.backendChatId) {
      // Normale Nachricht mit existierender Chat-ID
      this.callChatApi(message, currentChat);
    } else {
      // Sollte eigentlich nicht passieren (canSendMessage verhindert das ohne CSV/ID)
      this.isLoading = false;
    }
  }

  private callChatApi(message: string, chat: ChatSession): void {
    this.chatService.sendMessage(message, chat.backendChatId).subscribe({
      next: (response) => {
        this.handleApiResponse(
          response.response.bot_message,
          response.response.plot_reference ?? [],
          chat
        );
        this.isLoading = false;
      },
      error: (error) => {
        this.handleApiError(error, chat);
        this.isLoading = false;
      }
    });
  }

  private handleApiResponse(response: string, plotIndices: number[], chat: ChatSession): void {
    chat.messages.push({
      role: 'bot',
      content: response,
      renderedContent: this.renderMarkdown(response),
      timestamp: this.timeStamp(),
    });

    this.updateDerivedPanels(chat, response);
    this.attachPlots(chat, plotIndices);
    this.refreshView();
    this.scrollToBottom();
  }

  private handleApiError(error: any, chat: ChatSession): void {
    const errorMessage = error.message || 'Fehler bei der Kommunikation mit dem Backend';
    chat.messages.push({
      role: 'bot',
      content: `❌ ${errorMessage}`,
      renderedContent: this.escapeHtml(`❌ ${errorMessage}`),
      timestamp: this.timeStamp(),
    });
    this.refreshView();
    this.scrollToBottom();
  }

  private renderMarkdown(content: string): string {
    return marked.parse(content) as string;
  }

  private escapeHtml(content: string): string {
    return content
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;')
      .replace(/\n/g, '<br />');
  }

  private scrollToBottom(): void {
    if (this.chatWindow) {
      setTimeout(() => {
        this.chatWindow.nativeElement.scrollTop = this.chatWindow.nativeElement.scrollHeight;
      }, 0);
    }
  }

  private refreshView(): void {
    this.changeDetectorRef.detectChanges();
  }

  private timeStamp(): string {
    return new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }

  private updateDerivedPanels(chat: ChatSession, botMessage: string): void {
    const uploadedFile = chat.uploadedFileName ?? 'Keine CSV hochgeladen';

    chat.overview = `Datei: ${uploadedFile}. Aktiver Chat: ${chat.name}. Backend-Chat-ID: ${chat.backendChatId ?? 'noch nicht gesetzt'}.`;
    chat.summary = botMessage;
  }

  private attachPlots(chat: ChatSession, plotIndices: number[]): void {
    if (!chat.backendChatId || plotIndices.length === 0) {
      return;
    }

    const existingIndices = new Set(chat.plots.map((plot) => plot.index));
    const newPlots = plotIndices
      .filter((index) => !existingIndices.has(index))
      .map((index) => ({
        index,
        title: `Plot ${index}`,
        imageUrl: this.buildPlotUrl(chat.backendChatId!, index),
        available: true,
      }));

    chat.plots = [...chat.plots, ...newPlots];
  }

  markPlotUnavailable(chat: ChatSession, plotIndex: number): void {
    chat.plots = chat.plots.map((plot) =>
      plot.index === plotIndex ? { ...plot, available: false } : plot
    );
  }

  private buildPlotUrl(chatId: string, plotIndex: number): string {
    return `http://localhost:8000/chat/${chatId}/plots/${plotIndex}`;
  }
}
