import 'package:flutter/foundation.dart';

import '../models/sentiment_models.dart';
import '../services/sentiment_api_service.dart';

class SentimentProvider extends ChangeNotifier {
  SentimentProvider({
    required SentimentApiService apiService,
  }) : _apiService = apiService;

  final SentimentApiService _apiService;

  bool _isLoading = false;
  String? _errorMessage;
  String _currentKeyword = 'DeepSeek';
  final Set<SourcePlatform> _selectedSources = {
    SourcePlatform.youtube,
  };
  DashboardResponse _dashboard = _mockDashboard(keyword: 'DeepSeek');

  bool get isLoading => _isLoading;
  String? get errorMessage => _errorMessage;
  String get currentKeyword => _currentKeyword;
  DashboardResponse get dashboard => _dashboard;
  Set<SourcePlatform> get selectedSources => Set.unmodifiable(_selectedSources);

  void toggleSource(SourcePlatform source) {
    if (_selectedSources.contains(source)) {
      if (_selectedSources.length == 1) {
        return;
      }
      _selectedSources.remove(source);
    } else {
      _selectedSources.add(source);
    }
    notifyListeners();
  }

  Future<void> fetchDashboard({String? keyword}) async {
    final nextKeyword = (keyword ?? _currentKeyword).trim();
    if (nextKeyword.isEmpty) {
      return;
    }

    _currentKeyword = nextKeyword;
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      _dashboard = await _apiService.fetchDashboard(
        keyword: _currentKeyword,
        sources: _selectedSources,
      );
    } on SentimentApiException catch (error) {
      _errorMessage = error.message;
      _dashboard = _mockDashboard(keyword: _currentKeyword);
    } catch (error) {
      _errorMessage = 'Unexpected dashboard error: $error';
      _dashboard = _mockDashboard(keyword: _currentKeyword);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }
}

DashboardResponse _mockDashboard({required String keyword}) {
  return DashboardResponse(
    keyword: keyword,
    sentimentScore: 68,
    heatScore: 74,
    summary:
        'Most discussions lean cautiously positive, but users remain divided on pricing, reliability, and privacy tradeoffs.',
    controversyPoints: const [
      ControversyPoint(
        title: 'Pricing Pressure',
        summary: 'Users like the product direction, but many think subscription tiers are becoming too aggressive.',
        link: 'https://www.reddit.com/',
      ),
      ControversyPoint(
        title: 'Reliability vs Velocity',
        summary: 'Frequent feature drops are appreciated, yet crash reports and unstable builds are eroding trust.',
        link: 'https://www.youtube.com/',
      ),
      ControversyPoint(
        title: 'Privacy Concerns',
        summary: 'People are split on whether new recommendation features justify broader data collection.',
        link: 'https://news.ycombinator.com/',
      ),
    ],
    posts: const [
      SourcePost(
        title: 'Hands-on review says DeepSeek is fast but still uneven in output quality',
        content: 'Reviewer likes the speed and cost profile, but warns that benchmark wins do not always translate into stable real-world results.',
        author: 'AI Review Channel',
        originalLink: 'https://www.youtube.com/',
        source: 'youtube',
      ),
      SourcePost(
        title: 'DeepSeek comparison video questions coding reliability under pressure',
        content: 'The presenter is impressed by the pricing, but points out that edge cases still break more often than expected.',
        author: 'Model Lab',
        originalLink: 'https://www.youtube.com/',
        source: 'youtube',
      ),
      SourcePost(
        title: 'Video review praises features but raises privacy worries',
        content: 'The recommendations are smarter now, though the new permissions screen is worrying.',
        author: 'channel-commenter',
        originalLink: 'https://www.youtube.com/',
        source: 'youtube',
      ),
    ],
    retainedCommentCount: 18,
    discardedCommentCount: 3,
    sourceBreakdown: const {
      'youtube': 18,
      'x': 0,
    },
  );
}
