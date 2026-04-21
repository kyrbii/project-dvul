import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';

export interface ChatResponse {
  response: string;
}

export interface UploadResponse {
  response: string;
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
  sendMessage(message: string): Observable<ChatResponse> {
    return this.http.post<ChatResponse>(`${this.apiUrl}/chat`, { message })
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
