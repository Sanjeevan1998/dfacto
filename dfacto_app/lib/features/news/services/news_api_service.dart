import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/headline.dart';
import '../../../core/config/api_config.dart';

class NewsApiService {
  static const _baseUrl = ApiConfig.newsBaseUrl;

  Future<Map<String, dynamic>> getConfig() async {
    final response = await http
        .get(Uri.parse('$_baseUrl/config'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      return jsonDecode(response.body) as Map<String, dynamic>;
    }
    throw Exception('Failed to load config (${response.statusCode})');
  }

  Future<void> updateConfig(String keywords, int intervalMinutes) async {
    final response = await http
        .post(
          Uri.parse('$_baseUrl/config'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'keywords': keywords,
            'timer_interval': intervalMinutes,
          }),
        )
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) {
      throw Exception('Failed to update config (${response.statusCode})');
    }
  }

  Future<List<Headline>> getHeadlines({int limit = 50}) async {
    final response = await http
        .get(Uri.parse('$_baseUrl/headlines?limit=$limit'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode == 200) {
      final list = jsonDecode(response.body) as List<dynamic>;
      return list
          .map((e) => Headline.fromJson(e as Map<String, dynamic>))
          .toList();
    }
    throw Exception('Failed to load headlines (${response.statusCode})');
  }

  Future<void> triggerCrawler() async {
    final response = await http
        .post(Uri.parse('$_baseUrl/trigger'))
        .timeout(const Duration(seconds: 10));
    if (response.statusCode != 200) {
      throw Exception('Failed to trigger crawler (${response.statusCode})');
    }
  }
}
