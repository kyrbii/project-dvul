import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface ChatResponse {
  chat_id: string;
  response: {
    bot_message?: string;
    plot_reference?: number[];
    summary?: string;
    message?: string;
  };
}

export interface UploadResponse {
  chat_id: string;
}

export interface BackendPlot {
  title?: string;
  svg?: string;
}

export interface APIModel {
  short_name: string;
  long_name: string;
  local: boolean;
  paid: boolean;
}

export interface ModelsResponse {
  models: APIModel[];
}

export interface ChatPlotsResponse {
  chat_id: string;
  plots: BackendPlot[];
}

export interface ChatDescriptionResponse {
  chat_id?: string;
  description?: string;
  summary?: string;
  message?: string;
}

export interface ChatActivityEvent {
  index: number;
  type: string;
  message: string;
  tool_name?: string;
  tool_args?: Record<string, string>;
}

export interface ChatActivityResponse {
  chat_id: string;
  activity: ChatActivityEvent[];
}

export interface BackendChatSession {
  chat_id: string;
  name: string;
  uploaded_filename: string;
  description?: string;
  messages: any[];
  plots: any[];
  csv_preview?: {
    fileName: string;
    headers: string[];
    rows: string[][];
  };
  created_at: string;
  status: string;
}

export interface ChatsListResponse {
  chats: BackendChatSession[];
}

@Injectable({
  providedIn: 'root'
})
export class ChatService {
  private apiUrl = 'http://localhost:8000'; // Backend URL

  constructor(private http: HttpClient) { }

  // CSV-Datei hochladen und analysieren
  uploadCsv(file: File): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);

    return this.http.post<UploadResponse>(`${this.apiUrl}/upload-csv`, formData)
      .pipe(
        catchError(this.handleError)
      );
  }

  // Chat-Nachricht senden (nach CSV-Upload)
  sendMessage(message: string, chatId?: string, modelName?: string): Observable<ChatResponse> {
    const payload = {
      message,
      chat_id: chatId,
      model_name: modelName
    };
    return this.http.post<ChatResponse>(`${this.apiUrl}/chat`, payload)
      .pipe(
        catchError(this.handleError)
      );
  }

  getPlots(chatId: string): Observable<ChatPlotsResponse> {
    return this.http.get<ChatPlotsResponse>(`${this.apiUrl}/plots/${chatId}`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getDescription(chatId: string): Observable<ChatDescriptionResponse> {
    return this.http.get<ChatDescriptionResponse>(`${this.apiUrl}/description/${chatId}`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getActivity(chatId: string): Observable<ChatActivityResponse> {
    return this.http.get<ChatActivityResponse>(`${this.apiUrl}/activity/${chatId}`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getModels(): Observable<ModelsResponse> {
    return this.http.get<ModelsResponse>(`${this.apiUrl}/models`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getChats(): Observable<ChatsListResponse> {
    return this.http.get<ChatsListResponse>(`${this.apiUrl}/chats`)
      .pipe(
        catchError(this.handleError)
      );
  }

  getChatHistory(chatId: string): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/chat/${chatId}/history`)
      .pipe(
        catchError(this.handleError)
      );
  }

  // TODO: Später für kombinierte CSV + Text Nachrichten
  // sendCsvWithMessage(file: File, message: string): Observable<ChatResponse> {
  //   const formData = new FormData();
  //   formData.append('file', file);
  //   formData.append('message', message);
  //   return this.http.post<ChatResponse>(`${this.apiUrl}/combined-chat`, formData);
  // }

  private handleError(error: HttpErrorResponse) {
    let errorMessage = 'Ein unbekannter Fehler ist aufgetreten!';

    if (error.error instanceof ErrorEvent) {
      // Client-side error
      errorMessage = `Client Error: ${error.error.message}`;
    } else {
      // Server-side error
      errorMessage = `Server Error: ${error.status} - ${error.message}`;
    }

    console.error('API Error:', error);
    return throwError(() => new Error(errorMessage));
  }
}
