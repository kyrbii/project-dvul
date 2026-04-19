import { Component } from '@angular/core';

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

  constructor() {
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
    if (!this.selectedChat || !this.canSendMessage) {
      return;
    }

    const message = this.draftMessage.trim();
    const hasCsv = !!this.tempUploadedFile;
    const hasText = !!message;

    if (!hasCsv && !hasText) {
      return;
    }

    let content = '';
    if (hasCsv && hasText) {
      content = `CSV: ${this.tempUploadedFile!.name}\n${message}`;
    } else if (hasCsv) {
      content = `CSV: ${this.tempUploadedFile!.name}`;
    } else {
      content = message;
    }

    // Nachricht zum Chat hinzufügen
    this.selectedChat.messages.push({
      role: 'user',
      content: content,
      timestamp: this.timeStamp(),
    });

    // Bot-Antwort simulieren
    this.selectedChat.messages.push({
      role: 'bot',
      content: 'Antwort folgt. CSV-Analyse wird später hier integriert.',
      timestamp: this.timeStamp(),
    });

    // CSV dauerhaft im Chat speichern (nur beim ersten Mal)
    if (hasCsv && !this.selectedChat.uploadedFileName) {
      this.selectedChat.uploadedFileName = this.tempUploadedFile!.name;
    }

    // Temporäre Datei zurücksetzen
    this.tempUploadedFile = null;
    this.draftMessage = '';
  }

  private timeStamp(): string {
    return new Date().toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
  }
}
