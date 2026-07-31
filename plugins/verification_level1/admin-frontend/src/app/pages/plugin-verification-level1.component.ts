import { CommonModule } from '@angular/common';
import { Component, Input, OnChanges, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

interface Settings {
  enabled: boolean;
  verification_channel_id: number | null;
  verified_role_id: number | null;
  log_channel_id: number | null;
  nickname_mask: string;
  allow_reverification: boolean;
  alliance_uppercase: boolean;
  trim_values: boolean;
  max_alliance_length: number;
  max_nickname_length: number;
  verification_message: string;
  verification_button_text: string;
  slash_verify_enabled: boolean;
  slash_verify_name: string;
  prefix_verify_enabled: boolean;
  command_prefix: string;
  prefix_verify_name: string;
  slash_rename_enabled: boolean;
  slash_rename_name: string;
  prefix_rename_enabled: boolean;
  prefix_rename_name: string;
  allowed_channel_ids: number[];
  delete_user_command: boolean;
  cooldown_seconds: number;
  assign_role_on_verify: boolean;
  assign_role_on_rename: boolean;
  success_message_enabled: boolean;
  success_message_text: string;
  success_message_delete_after: number;
}

@Component({
  selector: 'app-verification-level1',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './verification-level1.component.html',
  styleUrls: ['./verification-level1.component.scss'],
})
export class VerificationLevel1Component implements OnChanges {
  @Input({ required: true }) guildId!: number;
  @Input() channels: Array<{ id: number; name: string }> = [];
  @Input() roles: Array<{ id: number; name: string }> = [];

  private http = inject(HttpClient);
  loading = false;
  saving = false;
  message = '';

  settings: Settings = {
    enabled: true,
    verification_channel_id: null,
    verified_role_id: null,
    log_channel_id: null,
    nickname_mask: '[{ALLIANCE}] {NICKNAME}',
    allow_reverification: true,
    alliance_uppercase: true,
    trim_values: true,
    max_alliance_length: 16,
    max_nickname_length: 24,
    verification_message: 'Натисніть кнопку нижче, щоб пройти верифікацію.',
    verification_button_text: 'Пройти верифікацію',
    slash_verify_enabled: true,
    slash_verify_name: 'verify',
    prefix_verify_enabled: true,
    command_prefix: '!',
    prefix_verify_name: 'verify',
    slash_rename_enabled: true,
    slash_rename_name: 'rename',
    prefix_rename_enabled: true,
    prefix_rename_name: 'rename',
    allowed_channel_ids: [],
    delete_user_command: true,
    cooldown_seconds: 30,
    assign_role_on_verify: true,
    assign_role_on_rename: true,
    success_message_enabled: true,
    success_message_text: '🎉 {MENTION}, вас успішно верифіковано!',
    success_message_delete_after: 300,
  };

  ngOnChanges(): void {
    if (this.guildId) this.load();
  }

  get preview(): string {
    return this.settings.nickname_mask
      .replaceAll('{ALLIANCE}', 'EVEX')
      .replaceAll('{NICKNAME}', 'Roman');
  }

  load(): void {
    this.loading = true;
    this.http
      .get<Settings>(`/api/plugins/verification-level1/${this.guildId}/settings`)
      .subscribe({
        next: value => {
          this.settings = { ...this.settings, ...value };
          this.loading = false;
        },
        error: error => {
          this.message = error?.error?.detail ?? 'Не вдалося завантажити налаштування';
          this.loading = false;
        },
      });
  }

  save(): void {
    this.saving = true;
    this.message = '';
    this.http
      .put<Settings>(
        `/api/plugins/verification-level1/${this.guildId}/settings`,
        this.settings,
      )
      .subscribe({
        next: value => {
          this.settings = value;
          this.message = 'Налаштування збережено';
          this.saving = false;
        },
        error: error => {
          this.message = error?.error?.detail ?? 'Помилка збереження';
          this.saving = false;
        },
      });
  }
}
