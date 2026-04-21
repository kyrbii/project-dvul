import { Component, ViewChild, ElementRef } from '@angular/core';
import { ChatService } from './chat.service';

interface ChatMessage {
  role: 'user' | 'bot';
  content: string;
  timestamp: string;
}

interface ChatSession {
  id: number;
  name: string;
  uploadedFileName?: string;
  messages: ChatMessage[];
  createdAt: string;
}

@Component({
  selector: 'app-root',
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

  constructor(private chatService: ChatService) {
    // Automatisch ersten Chat erstellen
    this.createNewChat();
  }

  get overviewText(): string {
    if (!this.selectedChat) {
      return 'Es wurde noch keine CSV Datei hochgeladen.';
    }
    return this.selectedChat.uploadedFileName
      ? `Aktuelle CSV: ${this.selectedChat.uploadedFileName}`
      : 'Noch keine CSV für diesen Chat ausgewählt.';
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
    const previousUploadedFileName = currentChat.uploadedFileName;
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
      timestamp: this.timeStamp(),
    });

    this.scrollToBottom();

    // Textfeld sofort leeren
    this.draftMessage = '';

    // API-Call machen
    if (hasCsv && uploadedFile) {
      // Direkt sperren, damit im aktiven Chat keine zweite CSV ausgewaehlt werden kann.
      currentChat.uploadedFileName = uploadedFile.name;

      // CSV uploaden
      this.chatService.uploadCsv(uploadedFile).subscribe({
        next: (response) => {
          this.handleApiResponse(response.response, currentChat);
          this.tempUploadedFile = null;
          this.draftMessage = '';
          this.isLoading = false;
        },
        error: (error) => {
          // uploadedFileName bleibt gesetzt, damit das Feld inaktiv bleibt
          this.handleApiError(error, currentChat);
          this.isLoading = false;
        }
      });
    } else {
      // Normale Chat-Nachricht
      this.chatService.sendMessage(message).subscribe({
        next: (response) => {
          this.handleApiResponse(response.response, currentChat);
          this.draftMessage = '';
          this.isLoading = false;
        },
        error: (error) => {
          this.handleApiError(error, currentChat);
          this.isLoading = false;
        }
      });
    }
  }

  private handleApiResponse(response: string, chat: ChatSession): void {
    chat.messages.push({
      role: 'bot',
      content: response,
      timestamp: this.timeStamp(),
    });
    this.scrollToBottom();
  }

  private handleApiError(error: any, chat: ChatSession): void {
    const errorMessage = error.message || 'Fehler bei der Kommunikation mit dem Backend';
    chat.messages.push({
      role: 'bot',
      content: `❌ ${errorMessage}`,
      timestamp: this.timeStamp(),
    });
    this.scrollToBottom();
  }

  private scrollToBottom(): void {
    if (this.chatWindow) {
      setTimeout(() => {
        this.chatWindow.nativeElement.scrollTop = this.chatWindow.nativeElement.scrollHeight;
      }, 0);
    }
  }

  private timeStamp(): string {
    return new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }
}
