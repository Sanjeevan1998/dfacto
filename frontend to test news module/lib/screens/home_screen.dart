import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final ApiService _apiService = ApiService();
  final TextEditingController _keywordsController = TextEditingController();
  final TextEditingController _intervalController = TextEditingController();

  List<dynamic> _headlines = [];
  bool _isLoading = false;
  String _errorMessage = '';

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });
    try {
      final config = await _apiService.getConfig();
      final headlines = await _apiService.getHeadlines();
      
      setState(() {
        _keywordsController.text = config['keywords'] ?? '';
        _intervalController.text = (config['timer_interval'] ?? 60).toString();
        _headlines = headlines;
        _isLoading = false;
      });
    } catch (e) {
      if (mounted) {
        setState(() {
            // Give a helpful message to run simulator
            _errorMessage = 'Failed to connect to backend server. Make sure it is running on port 8000.\n$e';
            _isLoading = false;
        });
      }
    }
  }

  Future<void> _updateConfig() async {
    try {
      final interval = int.parse(_intervalController.text);
      await _apiService.updateConfig(_keywordsController.text, interval);
      if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Configuration updated!')),
          );
      }
    } catch (e) {
      if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error updating config: $e')),
          );
      }
    }
  }

  Future<void> _triggerCrawlerNow() async {
    try {
        await _apiService.triggerCrawler();
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
              const SnackBar(content: Text('Crawler triggered! Press refresh in ~15 seconds to see results.')),
          );
        }
    } catch (e) {
         if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Error triggering crawler: $e')),
          );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Agentic Crawler'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadData,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                if (_errorMessage.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.all(8.0),
                    child: Text(_errorMessage, style: const TextStyle(color: Colors.red)),
                  ),
                  
                // Configuration Section
                Card(
                  margin: const EdgeInsets.all(16.0),
                  child: Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('Crawler Configuration', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 16),
                        TextField(
                          controller: _keywordsController,
                          decoration: const InputDecoration(
                            labelText: 'Keywords (e.g., AI, Tech)',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        TextField(
                          controller: _intervalController,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(
                            labelText: 'Timer Interval (minutes)',
                            border: OutlineInputBorder(),
                          ),
                        ),
                        const SizedBox(height: 16),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton(
                            onPressed: _updateConfig,
                            child: const Text('Save Configuration'),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
                
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                        const Text('Latest Headlines', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                        ElevatedButton.icon(
                            onPressed: _triggerCrawlerNow, 
                            icon: const Icon(Icons.play_arrow), 
                            label: const Text('Test Trigger Now')
                        )
                    ]
                  ),
                ),
                
                // Headlines List
                Expanded(
                  child: _headlines.isEmpty
                      ? const Center(child: Text('No headlines found.'))
                      : ListView.builder(
                          itemCount: _headlines.length,
                          itemBuilder: (context, index) {
                            final item = _headlines[index];
                            final currentKeyword = item['associated_keyword'] ?? 'Unknown Keyword';
                            final previousItemKeyword = index > 0 ? _headlines[index - 1]['associated_keyword'] : null;
                            
                            final bool isNewSection = index == 0 || currentKeyword != previousItemKeyword;

                            return Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                if (isNewSection)
                                  Padding(
                                    padding: const EdgeInsets.only(left: 16.0, top: 16.0, bottom: 8.0, right: 16.0),
                                    child: Text(
                                      'Phrase: $currentKeyword',
                                      style: const TextStyle(
                                        fontSize: 16,
                                        fontWeight: FontWeight.bold,
                                        color: Colors.deepPurpleAccent,
                                      ),
                                    ),
                                  ),
                                  Card(
                                    margin: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 4.0),
                                    clipBehavior: Clip.antiAlias,
                                    child: InkWell(
                                      onTap: () => _showDetailsDialog(context, item),
                                      child: Padding(
                                        padding: const EdgeInsets.all(12.0),
                                        child: Column(
                                          crossAxisAlignment: CrossAxisAlignment.start,
                                        children: [
                                          Text(
                                            item['title'] ?? 'No Title',
                                            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                                          ),
                                          const SizedBox(height: 4),
                                          Row(
                                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                            children: [
                                              Text(item['source'] ?? 'Unknown Source', style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                                              if (item['verdict'] != null && item['verdict'] != 'N/A')
                                                Chip(
                                                  label: Text(
                                                    '${item['verdict']}',
                                                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                                                  ),
                                                  // Colors dynamically change based on verdict
                                                  backgroundColor: item['verdict'] == 'TRUE'
                                                      ? Colors.green.withOpacity(0.2)
                                                      : item['verdict'] == 'FALSE'
                                                          ? Colors.red.withOpacity(0.2)
                                                          : item['verdict'] == 'MIXED'
                                                            ? Colors.orange.withOpacity(0.2)
                                                            : Colors.grey.withOpacity(0.2),
                                                  side: BorderSide.none,
                                                  padding: EdgeInsets.zero,
                                                )
                                            ],
                                          ),
                                          if (item['snippet'] != null && item['snippet'].toString().isNotEmpty)
                                            Padding(
                                              padding: const EdgeInsets.symmetric(vertical: 4.0),
                                              child: Text(item['snippet']!, maxLines: 2, overflow: TextOverflow.ellipsis),
                                            ),
                                          if (item['explanation'] != null && item['explanation'].toString().isNotEmpty)
                                            Container(
                                              margin: const EdgeInsets.only(top: 8.0, bottom: 4.0),
                                              padding: const EdgeInsets.all(8.0),
                                              decoration: BoxDecoration(
                                                color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.5),
                                                borderRadius: BorderRadius.circular(8.0),
                                                border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                                              ),
                                              child: Row(
                                                crossAxisAlignment: CrossAxisAlignment.start,
                                                children: [
                                                  const Icon(Icons.info_outline, size: 16, color: Colors.blueAccent),
                                                  const SizedBox(width: 8),
                                                  Expanded(
                                                    child: Text(
                                                      item['explanation']!,
                                                      style: const TextStyle(fontSize: 13, fontStyle: FontStyle.italic),
                                                    ),
                                                  ),
                                                ],
                                              ),
                                            ),
                                          const SizedBox(height: 4),
                                          Text(item['timestamp'] ?? '', style: const TextStyle(fontSize: 10, color: Colors.grey)),
                                        ],
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            );
                          },
                        ),
                ),
              ],
            ),
    );
  }

  void _showDetailsDialog(BuildContext context, dynamic item) {
    showDialog(
      context: context,
      builder: (context) {
        return AlertDialog(
          title: Text(item['title'] ?? 'No Title'),
          content: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisSize: MainAxisSize.min,
              children: [
                if (item['source'] != null)
                  Text('Source: ${item['source']}', style: const TextStyle(fontWeight: FontWeight.bold, color: Colors.grey)),
                const SizedBox(height: 8),
                if (item['snippet'] != null && item['snippet'].toString().isNotEmpty)
                  Text(item['snippet']!),
                const SizedBox(height: 12),
                if (item['explanation'] != null && item['explanation'].toString().isNotEmpty) ...[
                  const Text('Explanation:', style: TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 4),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12.0),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.surfaceVariant.withOpacity(0.5),
                      borderRadius: BorderRadius.circular(8.0),
                      border: Border.all(color: Theme.of(context).colorScheme.outlineVariant),
                    ),
                    child: Text(
                      item['explanation']!,
                      style: const TextStyle(fontSize: 14, fontStyle: FontStyle.italic),
                    ),
                  ),
                ],
                const SizedBox(height: 12),
                if (item['timestamp'] != null)
                  Text('Timestamp: ${item['timestamp']}', style: const TextStyle(fontSize: 12, color: Colors.grey)),
                const SizedBox(height: 12),
                if (item['verdict'] != null && item['verdict'] != 'N/A')
                  Row(
                    children: [
                      const Text('Verdict: ', style: TextStyle(fontWeight: FontWeight.bold)),
                      Chip(
                        label: Text(
                          '${item['verdict']}',
                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
                        ),
                        backgroundColor: item['verdict'] == 'TRUE'
                            ? Colors.green.withOpacity(0.2)
                            : item['verdict'] == 'FALSE'
                                ? Colors.red.withOpacity(0.2)
                                : item['verdict'] == 'MIXED'
                                  ? Colors.orange.withOpacity(0.2)
                                  : Colors.grey.withOpacity(0.2),
                        side: BorderSide.none,
                      ),
                    ],
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Close'),
            ),
          ],
        );
      },
    );
  }
}
