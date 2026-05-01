import { ChangeDetectorRef, Component, ViewChild, ElementRef } from '@angular/core';
import { BackendPlot, ChatDescriptionResponse, ChatService, ChatResponse } from './chat.service';
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
  renderedSummary?: string;
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
      return 'Hier wird nach dem Hochladen der CSV die Zusammenfassung angezeigt.';
    }

    return this.selectedChat.summary
      ?? 'Hier wird nach dem Hochladen der CSV die Zusammenfassung angezeigt.';
  }

  get renderedSummaryText(): string {
    return this.selectedChat?.renderedSummary ?? this.renderMarkdown(this.summaryText);
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
      renderedSummary: this.renderMarkdown('Hier wird nach dem Hochladen der CSV die Zusammenfassung angezeigt.'),
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
          this.refreshDescription(currentChat);

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
        this.handleApiResponse(response, chat);
      },
      error: (error) => {
        this.handleApiError(error, chat);
        this.isLoading = false;
      }
    });
  }

  private handleApiResponse(apiResponse: ChatResponse, chat: ChatSession): void {
    const response = this.extractBotMessage(apiResponse);
    const plotIndices = apiResponse.response.plot_reference ?? [];

    chat.messages.push({
      role: 'bot',
      content: response,
      renderedContent: this.renderMarkdown(response),
      timestamp: this.timeStamp(),
    });

    this.updateDerivedPanels(chat, response);
    this.refreshDescription(chat, response);
    this.syncPlots(chat, plotIndices);
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
    this.setSummary(chat, botMessage);
  }

  private refreshDescription(chat: ChatSession, fallbackMessage?: string): void {
    if (!chat.backendChatId) {
      return;
    }

    this.chatService.getDescription(chat.backendChatId).subscribe({
      next: (descriptionResponse) => {
        const description = this.extractDescription(descriptionResponse);
        if (description) {
          this.setSummary(chat, description);
          this.refreshView();
        }
      },
      error: () => {
        if (fallbackMessage) {
          this.setSummary(chat, fallbackMessage);
          this.refreshView();
        }
      },
    });
  }

  private setSummary(chat: ChatSession, summary: string): void {
    chat.summary = summary;
    chat.renderedSummary = this.renderMarkdown(summary);
  }

  private extractDescription(descriptionResponse: ChatDescriptionResponse): string {
    return descriptionResponse.description
      ?? descriptionResponse.summary
      ?? descriptionResponse.message
      ?? '';
  }

  private syncPlots(chat: ChatSession, fallbackIndices: number[]): void {
    if (!chat.backendChatId) {
      this.finalizeResponse();
      return;
    }

    this.chatService.getPlots(chat.backendChatId).subscribe({
      next: ({ plots }) => {
        chat.plots = this.mapBackendPlots(chat.backendChatId!, plots, fallbackIndices);
        this.finalizeResponse();
      },
      error: () => {
        this.attachPlotsByIndices(chat, fallbackIndices);
        this.finalizeResponse();
      }
    });
  }

  private mapBackendPlots(chatId: string, plots: BackendPlot[], fallbackIndices: number[]): ChatPlot[] {
    if (!plots.length) {
      return this.buildFallbackPlots(chatId, fallbackIndices);
    }

    return plots.map((plot, index) => ({
      index: index + 1,
      title: plot.title?.trim() || `Plot ${index + 1}`,
      imageUrl: this.buildPlotUrl(chatId, index + 1),
      available: true,
    }));
  }

  private attachPlotsByIndices(chat: ChatSession, plotIndices: number[]): void {
    if (!chat.backendChatId || plotIndices.length === 0) {
      return;
    }

    chat.plots = this.buildFallbackPlots(chat.backendChatId, plotIndices);
  }

  private buildFallbackPlots(chatId: string, plotIndices: number[]): ChatPlot[] {
    return plotIndices.map((index) => ({
      index,
      title: `Plot ${index}`,
      imageUrl: this.buildPlotUrl(chatId, index),
      available: true,
    }));
  }

  private extractBotMessage(apiResponse: ChatResponse): string {
    return apiResponse.response.bot_message
      ?? apiResponse.response.summary
      ?? apiResponse.response.message
      ?? 'Das Backend hat keine Antwort geliefert.';
  }

  private finalizeResponse(): void {
    this.isLoading = false;
    this.refreshView();
    this.scrollToBottom();
  }

  markPlotUnavailable(chat: ChatSession, plotIndex: number): void {
    chat.plots = chat.plots.map((plot) =>
      plot.index === plotIndex ? { ...plot, available: false } : plot
    );
  }

  private buildPlotUrl(chatId: string, plotIndex: number): string {
    return `http://localhost:8000/plots/${chatId}/${plotIndex}`;
  }
}
