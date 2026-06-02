import { ChangeDetectorRef, Component, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { BackendPlot, ChatActivityEvent, ChatDescriptionResponse, ChatService, ChatResponse, APIModel } from './chat.service';
import { marked } from 'marked';

interface ChatMessage {
  role: 'user' | 'bot';
  content: string;
  renderedContent?: string;
  timestamp: string;
  isThinking?: boolean;
}

interface ChatPlot {
  index: number;
  title: string;
  imageUrl: string;
  available: boolean;
}

interface CsvPreview {
  fileName: string;
  headers: string[];
  rows: string[][];
}

interface ChatSession {
  id: number;
  name: string;
  uploadedFileName?: string;
  csvPreview?: CsvPreview;
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
export class AppComponent implements OnInit, OnDestroy {
  draftMessage = '';
  selectedChat: ChatSession | null = null;
  chats: ChatSession[] = [];
  nextChatId = 1;
  tempUploadedFile: File | null = null; // Temporäre CSV-Datei
  tempCsvPreview: CsvPreview | null = null;
  isLoading = false; // Für Ladezustand

  models: APIModel[] = [];
  selectedModel = '';
  isModelsLoading = false;
  maximizedPlot: ChatPlot | null = null;

  private activeThinkingChat: ChatSession | null = null;
  private activeThinkingMessage: ChatMessage | null = null;
  private thinkingIntervalId: ReturnType<typeof setInterval> | null = null;
  private activityPollingIntervalId: ReturnType<typeof setInterval> | null = null;
  private activeActivityIndex = 0;
  private receivedBackendActivity = false;
  private thinkingStepIndex = 0;
  private thinkingSteps: string[] = [];

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

  ngOnInit(): void {
    this.loadModels();
  }

  loadModels(): void {
    this.isModelsLoading = true;
    this.chatService.getModels().subscribe({
      next: (response) => {
        this.models = response.models || [];
        if (this.models.length > 0) {
          this.selectedModel = this.models[0].long_name;
        }
        this.isModelsLoading = false;
        this.refreshView();
      },
      error: (error) => {
        console.error('Failed to load active models from backend', error);
        this.models = [
          {
            short_name: "Standard-Modell",
            long_name: "default",
            local: false,
            paid: false
          }
        ];
        this.selectedModel = "default";
        this.isModelsLoading = false;
        this.refreshView();
      }
    });
  }

  ngOnDestroy(): void {
    this.clearThinkingTimer();
    this.clearActivityPolling();
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

  get showCsvPreview(): boolean {
    return !!this.selectedChat?.csvPreview;
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
    this.tempCsvPreview = null;
    this.draftMessage = '';
  }

  selectChat(chat: ChatSession): void {
    this.selectedChat = chat;
    this.tempUploadedFile = null; // Temporäre Datei zurücksetzen beim Chat-Wechsel
    this.tempCsvPreview = null;
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
    this.tempCsvPreview = {
      fileName: file.name,
      headers: [],
      rows: [],
    };
    this.readCsvPreview(file, this.selectedChat);

    // Chat-Namen setzen, wenn noch nicht geschehen
    if (!this.selectedChat.uploadedFileName) {
      this.selectedChat.name = file.name.replace('.csv', '');
    }

    input.value = '';
  }

  removeCsv(): void {
    this.tempUploadedFile = null;
    this.tempCsvPreview = null;
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
    if (hasText) {
      userContent = message;
    } else if (hasCsv) {
      userContent = `Datei hochgeladen: ${uploadedFile!.name}`;
    }

    currentChat.messages.push({
      role: 'user',
      content: userContent,
      renderedContent: this.escapeHtml(userContent),
      timestamp: this.timeStamp(),
    });
    this.showThinkingMessage(currentChat, hasCsv);

    this.scrollToBottom();

    // Textfeld sofort leeren
    this.draftMessage = '';

    // API-Call machen
    if (hasCsv && uploadedFile) {
      // Direkt sperren, damit im aktiven Chat keine zweite CSV ausgewaehlt werden kann.
      currentChat.uploadedFileName = uploadedFile.name;
      currentChat.csvPreview = this.tempCsvPreview ?? {
        fileName: uploadedFile.name,
        headers: [],
        rows: [],
      };

      this.chatService.uploadCsv(uploadedFile).subscribe({
        next: (uploadResponse) => {
          currentChat.backendChatId = uploadResponse.chat_id;
          this.tempUploadedFile = null;
          this.tempCsvPreview = null;

          //Beschreibung wird nach der Antwort aktualisiert.
          this.callChatApi(message, currentChat, this.selectedModel);
        },
        error: (error) => {
          this.handleApiError(error, currentChat);
          this.isLoading = false;
        }
      });
    } else if (currentChat.backendChatId) {
      // Normale Nachricht mit existierender Chat-ID
      this.callChatApi(message, currentChat, this.selectedModel);
    } else {
      // Sollte eigentlich nicht passieren (canSendMessage verhindert das ohne CSV/ID)
      this.isLoading = false;
    }
  }

  private callChatApi(message: string, chat: ChatSession, modelName: string): void {
    this.startActivityPolling(chat);

    this.chatService.sendMessage(message, chat.backendChatId, modelName).subscribe({
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

    this.removeThinkingMessage(chat);

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

  private showThinkingMessage(chat: ChatSession, includesCsv: boolean): void {
    this.clearThinkingTimer();

    this.thinkingSteps = includesCsv
      ? [
        'CSV wird hochgeladen und vorbereitet',
        'Spalten und Datentypen werden geprüft',
        'Auffälligkeiten und erste Muster werden gesucht',
        'Antwort wird formuliert',
      ]
      : [
        'Frage wird eingeordnet',
        'Passende Informationen aus dem Datensatz werden gesucht',
        'Antwort wird formuliert',
      ];
    this.thinkingStepIndex = 0;

    const thinkingMessage: ChatMessage = {
      role: 'bot',
      content: this.thinkingSteps[0],
      renderedContent: this.escapeHtml(this.thinkingSteps[0]),
      timestamp: this.timeStamp(),
      isThinking: true,
    };

    chat.messages.push(thinkingMessage);
    this.activeThinkingChat = chat;
    this.activeThinkingMessage = thinkingMessage;
    this.thinkingIntervalId = setInterval(() => {
      this.advanceThinkingMessage();
    }, 2200);
  }

  private advanceThinkingMessage(): void {
    if (!this.activeThinkingMessage || this.thinkingSteps.length === 0 || this.receivedBackendActivity) {
      return;
    }

    this.thinkingStepIndex = (this.thinkingStepIndex + 1) % this.thinkingSteps.length;
    const nextStep = this.thinkingSteps[this.thinkingStepIndex];
    this.activeThinkingMessage.content = nextStep;
    this.activeThinkingMessage.renderedContent = this.escapeHtml(nextStep);
    this.refreshView();
    this.scrollToBottom();
  }

  private removeThinkingMessage(chat: ChatSession): void {
    this.clearThinkingTimer();
    this.clearActivityPolling();

    if (this.activeThinkingChat === chat && this.activeThinkingMessage) {
      chat.messages = chat.messages.filter((message) => message !== this.activeThinkingMessage);
    }

    this.activeThinkingChat = null;
    this.activeThinkingMessage = null;
    this.activeActivityIndex = 0;
    this.receivedBackendActivity = false;
  }

  private clearThinkingTimer(): void {
    if (this.thinkingIntervalId) {
      clearInterval(this.thinkingIntervalId);
      this.thinkingIntervalId = null;
    }
  }

  private startActivityPolling(chat: ChatSession): void {
    if (!chat.backendChatId) {
      return;
    }

    this.clearActivityPolling();
    this.activeActivityIndex = 0;
    this.receivedBackendActivity = false;
    this.pollActivity(chat);
    this.activityPollingIntervalId = setInterval(() => {
      this.pollActivity(chat);
    }, 1000);
  }

  private pollActivity(chat: ChatSession): void {
    if (!chat.backendChatId || !this.activeThinkingMessage) {
      return;
    }

    this.chatService.getActivity(chat.backendChatId).subscribe({
      next: ({ activity }) => {
        const nextEvents = activity.filter((event) => event.index > this.activeActivityIndex);
        if (!nextEvents.length) {
          return;
        }

        const latestEvent = nextEvents[nextEvents.length - 1];
        this.activeActivityIndex = latestEvent.index;
        this.updateThinkingMessageFromActivity(latestEvent);
      },
      error: () => {
        // Activity polling is progressive enhancement; the chat response still handles errors.
      }
    });
  }

  private updateThinkingMessageFromActivity(event: ChatActivityEvent): void {
    if (!this.activeThinkingMessage) {
      return;
    }

    this.receivedBackendActivity = true;
    this.activeThinkingMessage.content = event.message;
    this.activeThinkingMessage.renderedContent = this.escapeHtml(event.message);
    this.refreshView();
    this.scrollToBottom();
  }

  private clearActivityPolling(): void {
    if (this.activityPollingIntervalId) {
      clearInterval(this.activityPollingIntervalId);
      this.activityPollingIntervalId = null;
    }
  }

  private readCsvPreview(file: File, chat: ChatSession): void {
    const reader = new FileReader();

    reader.onload = () => {
      const text = String(reader.result ?? '');
      const preview = this.buildCsvPreview(file.name, text);

      if (this.tempUploadedFile?.name === file.name) {
        this.tempCsvPreview = preview;
      }

      if (chat.uploadedFileName === file.name) {
        chat.csvPreview = preview;
      }

      this.refreshView();
    };

    reader.readAsText(file);
  }

  private buildCsvPreview(fileName: string, csvText: string): CsvPreview {
    const lines = csvText
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .slice(0, 3);
    const delimiter = this.detectCsvDelimiter(lines[0] ?? '');
    const parsedLines = lines.map((line) => this.parseCsvLine(line, delimiter));
    const headers = parsedLines[0] ?? [];

    return {
      fileName,
      headers,
      rows: parsedLines.slice(1, 3),
    };
  }

  private detectCsvDelimiter(headerLine: string): string {
    const semicolonCount = this.parseCsvLine(headerLine, ';').length;
    const commaCount = this.parseCsvLine(headerLine, ',').length;

    return semicolonCount > commaCount ? ';' : ',';
  }

  private parseCsvLine(line: string, delimiter = ','): string[] {
    const values: string[] = [];
    let current = '';
    let inQuotes = false;

    for (let index = 0; index < line.length; index++) {
      const character = line[index];
      const nextCharacter = line[index + 1];

      if (character === '"' && inQuotes && nextCharacter === '"') {
        current += '"';
        index++;
      } else if (character === '"') {
        inQuotes = !inQuotes;
      } else if (character === delimiter && !inQuotes) {
        values.push(current);
        current = '';
      } else {
        current += character;
      }
    }

    values.push(current);
    return values;
  }

  private handleApiError(error: any, chat: ChatSession): void {
    this.removeThinkingMessage(chat);
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

  maximizePlot(plot: ChatPlot): void {
    this.maximizedPlot = plot;
    this.refreshView();
  }

  closeMaximizedPlot(): void {
    this.maximizedPlot = null;
    this.refreshView();
  }

  private buildPlotUrl(chatId: string, plotIndex: number): string {
    return `http://localhost:8000/plots/${chatId}/${plotIndex}`;
  }
}
