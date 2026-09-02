interface ApiErrorEnvelope {
  error?: {
    code?: unknown;
    message?: unknown;
    details?: unknown;
    request_id?: unknown;
  };
}

export class MandacorApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number | null,
    public readonly details: Record<string, unknown> = {},
    public readonly requestId: string | null = null,
  ) {
    super(message);
    this.name = 'MandacorApiError';
  }
}

export function parseApiError(status: number, payload: unknown): MandacorApiError {
  const envelope = payload as ApiErrorEnvelope;
  const code = typeof envelope?.error?.code === 'string' ? envelope.error.code : 'API_ERROR';
  const message =
    typeof envelope?.error?.message === 'string'
      ? envelope.error.message
      : 'O servidor MANDACOR recusou a solicitação.';
  const details =
    envelope?.error?.details && typeof envelope.error.details === 'object'
      ? (envelope.error.details as Record<string, unknown>)
      : {};
  const requestId = typeof envelope?.error?.request_id === 'string' ? envelope.error.request_id : null;
  return new MandacorApiError(code, message, status, details, requestId);
}

const friendlyMessages: Record<string, string> = {
  API_OFFLINE: 'Servidor MANDACOR offline.',
  INSTRUMENT_UNAVAILABLE: 'Espectrofotômetro indisponível.',
  INSTRUMENT_DISCONNECTED: 'O espectrofotômetro está desconectado.',
  SESSION_NOT_READY: 'A sessão ainda não está pronta.',
  SESSION_NOT_FOUND: 'A sessão não existe mais no servidor.',
  OPERATION_NOT_FOUND: 'A operação não existe mais no servidor.',
  MEASUREMENT_TIMEOUT: 'Nenhuma nova leitura foi detectada.',
  CAPTURE_CANCELLED: 'A espera pela leitura foi cancelada.',
  CAPTURE_ALREADY_ACTIVE: 'Já existe uma captura ativa nesta sessão.',
  TARGET_REQUIRED: 'Capture a cor alvo antes da amostra.',
  LATEST_MEASUREMENT_ALREADY_SELECTED: 'A última leitura do espectrofotômetro já está selecionada.',
  FORMULA_READING_ALREADY_SAVED: 'Esta leitura já foi salva no dataset de uma cor.',
  MEASUREMENT_ROLE_CONFLICT: 'A mesma leitura não pode ser usada como alvo e amostra.',
  SESSION_MEASUREMENTS_LOCKED: 'As leituras não podem ser trocadas depois que um ajuste foi registrado.',
  MULTIPLE_INSTRUMENTS: 'Escolha qual instrumento deseja conectar.',
  HOST_REQUIRED: 'Informe o IP do espectrofotômetro.',
  REQUEST_TIMEOUT: 'O servidor demorou demais para responder.',
  AFTER_MEASUREMENT_TIMEOUT_ADJUSTMENT_ALREADY_APPLIED: 'AFTER não detectado. O ajuste continua aplicado; não adicione o pigmento novamente.',
  PENDING_ADJUSTMENT_EXISTS: 'Existe um ajuste aplicado aguardando leitura AFTER.',
  ADJUSTMENT_NOT_COMPLETED: 'O ajuste ainda não foi concluído.',
  ADJUSTMENT_INVALID_STATE: 'O ajuste não permite esta operação no estado atual.',
  SERVER_VERSION_INCOMPATIBLE: 'VERSÃO DO SERVIDOR INCOMPATÍVEL.',
  RECOVERY_FILE_INVALID: 'O estado físico precisa ser verificado. O arquivo de recuperação está inválido.',
  INTERNAL_SERVER_ERROR: 'O servidor encontrou um erro inesperado.',
};

export function friendlyError(error: unknown): string {
  if (error instanceof MandacorApiError) {
    return friendlyMessages[error.code] ?? error.message;
  }
  return 'Não foi possível concluir a operação.';
}
