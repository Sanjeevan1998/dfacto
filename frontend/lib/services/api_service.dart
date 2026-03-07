import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  // Use 10.0.2.2 for Android emulator, localhost for iOS simulator
  static const String baseUrl = 'http://localhost:8000';

  Future<Map<String, dynamic>> getConfig() async {
    final response = await http.get(Uri.parse('$baseUrl/config'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to load config');
    }
  }

  Future<void> updateConfig(String keywords, int interval) async {
    final response = await http.post(
      Uri.parse('$baseUrl/config'),
      headers: {'Content-Type': 'application/json'},
      body: json.encode({
        'keywords': keywords,
        'timer_interval': interval,
      }),
    );
    if (response.statusCode != 200) {
      throw Exception('Failed to update config');
    }
  }

  Future<List<dynamic>> getHeadlines() async {
    final response = await http.get(Uri.parse('$baseUrl/headlines'));
    if (response.statusCode == 200) {
      return json.decode(response.body);
    } else {
      throw Exception('Failed to load headlines');
    }
  }

  Future<void> triggerCrawler() async {
    final response = await http.post(Uri.parse('$baseUrl/trigger'));
    if (response.statusCode != 200) {
      throw Exception('Failed to trigger crawler');
    }
  }
}
