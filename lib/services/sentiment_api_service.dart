import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../models/sentiment_models.dart';

class SentimentApiService {
  SentimentApiService({
    String? baseUrl,
    http.Client? client,
  })  : baseUrl = baseUrl ?? _resolveBaseUrl(),
        _client = client;

  static String _resolveBaseUrl() {
    const configuredBaseUrl = String.fromEnvironment('API_BASE_URL');
    if (configuredBaseUrl.isNotEmpty) {
      return configuredBaseUrl;
    }

    if (kIsWeb) {
      return 'http://127.0.0.1:8000';
    }

    if (Platform.isAndroid) {
      return 'http://10.0.2.2:8000';
    }

    return 'http://127.0.0.1:8000';
  }

  final String baseUrl;
  final http.Client? _client;

  Future<DashboardResponse> fetchDashboard({
    required String keyword,
    required Set<SourcePlatform> sources,
  }) async {
    final client = _client ?? http.Client();
    try {
      final response = await client
          .post(
            Uri.parse('$baseUrl/api/analyze'),
            headers: const {'Content-Type': 'application/json'},
            body: jsonEncode({
              'keyword': keyword,
              'sources': sources.map((source) => source.value).toList(),
            }),
          )
          .timeout(const Duration(seconds: 90));
      if (response.statusCode != 200) {
        throw SentimentApiException(
          'Backend returned ${response.statusCode}: ${response.body}',
        );
      }

      final decoded = jsonDecode(response.body) as Map<String, dynamic>;
      return DashboardResponse.fromJson(decoded);
    } on SocketException catch (error) {
      throw SentimentApiException(
        'Backend is unreachable at $baseUrl. '
        'Android emulator should use http://10.0.2.2:8000; desktop should use http://127.0.0.1:8000; real devices should use your PC LAN IP. '
        'SocketException: $error',
      );
    } on http.ClientException catch (error) {
      throw SentimentApiException(
        'HTTP client failed to reach $baseUrl. '
        'If you are using the Android emulator keep API_BASE_URL as http://10.0.2.2:8000. '
        'If you are using a real device, switch to your PC LAN IP. '
        'ClientException: $error',
      );
    } catch (error) {
      throw SentimentApiException(
        'Failed to load dashboard data: $error',
      );
    } finally {
      if (_client == null) {
        client.close();
      }
    }
  }
}

class SentimentApiException implements Exception {
  const SentimentApiException(this.message);

  final String message;

  @override
  String toString() => message;
}
