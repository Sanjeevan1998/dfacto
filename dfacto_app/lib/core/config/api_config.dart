class ApiConfig {
  ApiConfig._();

  /// Live Audit WebSocket backend (dfacto_backend)
  static const String liveAuditWsHost = '192.168.1.158';
  static const int liveAuditPort = 8000;

  /// News Crawler backend (backend for news module) — runs on port 8001
  static const String newsBaseUrl = 'http://192.168.1.158:8001';
}
