import 'dart:async';

import 'package:flutter/foundation.dart';

import '../models/sentiment_models.dart';
import 'app_language_provider.dart';
import '../services/sentiment_api_service.dart';

class SentimentProvider extends ChangeNotifier {
  SentimentProvider({
    required SentimentApiService apiService,
  }) : _apiService = apiService;

  final SentimentApiService _apiService;
  static const String _defaultLlmModel = 'deepseek-chat';
  static const List<Duration> monitoringIntervals = <Duration>[
    Duration(minutes: 10),
    Duration(minutes: 30),
    Duration(hours: 1),
    Duration(hours: 3),
    Duration(hours: 6),
    Duration(hours: 12),
    Duration(days: 1),
    Duration(days: 2),
  ];

  bool _isLoading = false;
  String? _errorMessage;
  String _currentKeyword = '';
  int _totalFetchLimit = 20;
  YouTubeCollectionMode _youtubeMode = YouTubeCollectionMode.officialApi;
  AppLanguage _outputLanguage = AppLanguage.english;
  Timer? _monitoringTimer;
  Timer? _monitoringCountdownTimer;
  Timer? _loadingProgressResetTimer;
  bool _monitoringEnabled = false;
  Duration _monitoringInterval = monitoringIntervals.first;
  DateTime? _monitoringStartedAt;
  DateTime? _nextMonitoringTriggerAt;
  int _monitoringTriggerCount = 0;
  int? _pendingSentimentAlertScore;
  List<MonitorStage> _loadingMonitorStages = const [];
  final Set<SourcePlatform> _selectedSources = {
    SourcePlatform.youtube,
  };
  final Map<SourcePlatform, SourceWeightTier> _sourceWeights = {
    for (final source in SourcePlatform.values) source: SourceWeightTier.medium,
  };
  DashboardResponse? _dashboard;

  bool get isLoading => _isLoading;
  bool get showLoadingProgress => _isLoading || _loadingMonitorStages.isNotEmpty;
  bool get configurationLocked => _isLoading || _monitoringEnabled;
  String? get errorMessage => _errorMessage;
  String get currentKeyword => _currentKeyword;
  int get totalFetchLimit => _totalFetchLimit;
  YouTubeCollectionMode get youtubeMode => _youtubeMode;
  AppLanguage get outputLanguage => _outputLanguage;
  bool get monitoringEnabled => _monitoringEnabled;
  Duration get monitoringInterval => _monitoringInterval;
  DateTime? get monitoringStartedAt => _monitoringStartedAt;
  DateTime? get nextMonitoringTriggerAt => _nextMonitoringTriggerAt;
  int get monitoringTriggerCount => _monitoringTriggerCount;
  Duration? get monitoringRemaining {
    final nextTriggerAt = _nextMonitoringTriggerAt;
    if (!_monitoringEnabled || nextTriggerAt == null) {
      return null;
    }
    final remaining = nextTriggerAt.difference(DateTime.now());
    if (remaining.isNegative) {
      return Duration.zero;
    }
    return remaining;
  }
  bool get hasPendingSentimentAlert => _pendingSentimentAlertScore != null;
  int? get pendingSentimentAlertScore => _pendingSentimentAlertScore;
  DashboardResponse? get dashboard => _dashboard;
  bool get hasDashboard => _dashboard != null;
  Set<SourcePlatform> get selectedSources => Set.unmodifiable(_selectedSources);
  Map<SourcePlatform, SourceWeightTier> get sourceWeights =>
      Map.unmodifiable(_sourceWeights);
  List<MonitorStage> get loadingMonitorStages =>
      List.unmodifiable(_loadingMonitorStages);
  List<String> get loadingSteps => List.unmodifiable(_buildLoadingSteps());
  int get loadingStepIndex => _resolveLoadingStepIndex(_loadingMonitorStages);
  String? get currentLoadingStep {
    final steps = _buildLoadingSteps();
    if (steps.isEmpty) {
      return null;
    }
    return steps[_resolveLoadingStepIndex(_loadingMonitorStages)];
  }

  void toggleSource(SourcePlatform source) {
    if (configurationLocked) {
      return;
    }
    if (source == SourcePlatform.x) {
      return;
    }
    if (_selectedSources.contains(source)) {
      if (_selectedSources.length == 1) {
        return;
      }
      _selectedSources.remove(source);
    } else {
      _selectedSources.add(source);
    }
    if (_totalFetchLimit < _selectedSources.length) {
      _totalFetchLimit = _selectedSources.length;
    }
    notifyListeners();
  }

  void setTotalFetchLimit(int value) {
    if (configurationLocked) {
      return;
    }
    final minimum = _selectedSources.length;
    _totalFetchLimit = value.clamp(minimum, 50).toInt();
    notifyListeners();
  }

  void setSourceWeight(SourcePlatform source, SourceWeightTier tier) {
    if (configurationLocked) {
      return;
    }
    _sourceWeights[source] = tier;
    notifyListeners();
  }

  void setYouTubeMode(YouTubeCollectionMode mode) {
    if (configurationLocked) {
      return;
    }
    _youtubeMode = mode;
    notifyListeners();
  }

  void setOutputLanguage(AppLanguage language) {
    if (configurationLocked) {
      return;
    }
    _outputLanguage = language;
    notifyListeners();
  }

  void setMonitoringInterval(Duration value) {
    if (_monitoringEnabled) {
      return;
    }
    _monitoringInterval = value;
    notifyListeners();
  }

  void toggleMonitoring({
    required String keyword,
  }) {
    if (_monitoringEnabled) {
      _stopMonitoring();
      notifyListeners();
      return;
    }

    final normalizedKeyword = keyword.trim().isNotEmpty
        ? keyword.trim()
        : _currentKeyword.trim();
    if (normalizedKeyword.isEmpty) {
      _errorMessage = 'Enter a keyword before enabling monitoring.';
      notifyListeners();
      return;
    }

    _currentKeyword = normalizedKeyword;
    _monitoringEnabled = true;
    _monitoringStartedAt = DateTime.now();
    _monitoringTriggerCount = 0;
    _errorMessage = null;
    _startMonitoringCountdownTicker();
    _scheduleNextMonitoringTrigger(_monitoringInterval);
    notifyListeners();
  }

  void clearPendingSentimentAlert() {
    _pendingSentimentAlertScore = null;
    notifyListeners();
  }

  Future<void> fetchDashboard({
    String? keyword,
    bool triggeredByMonitoring = false,
  }) async {
    final nextKeyword = (keyword ?? _currentKeyword).trim();
    if (nextKeyword.isEmpty) {
      return;
    }

    _currentKeyword = nextKeyword;
    _loadingProgressResetTimer?.cancel();
    _loadingProgressResetTimer = null;
    _isLoading = true;
    _errorMessage = null;
    _loadingMonitorStages = const [];
    notifyListeners();

    try {
      _dashboard = await _apiService.fetchDashboard(
        keyword: _currentKeyword,
        sources: _selectedSources,
        totalLimit: _totalFetchLimit,
        sourceWeights: {
          for (final source in _selectedSources) source: _sourceWeights[source]!,
        },
        youtubeMode: _youtubeMode,
        outputLanguage: _outputLanguage,
      );
      _loadingMonitorStages = _dashboard?.monitorStages ?? const [];
      notifyListeners();
      await Future<void>.delayed(const Duration(milliseconds: 900));
      if (triggeredByMonitoring &&
          (_dashboard?.sentimentScore ?? 100) < 30) {
        _pendingSentimentAlertScore = _dashboard?.sentimentScore;
      }
    } on SentimentApiException catch (error) {
      _errorMessage = error.message;
    } catch (error) {
      _errorMessage = 'Unexpected dashboard error: $error';
    } finally {
      _isLoading = false;
      notifyListeners();
      if (_loadingMonitorStages.isNotEmpty) {
        _scheduleLoadingProgressReset();
      }
    }
  }

  @override
  void dispose() {
    _monitoringTimer?.cancel();
    _monitoringCountdownTimer?.cancel();
    _loadingProgressResetTimer?.cancel();
    super.dispose();
  }

  void _scheduleLoadingProgressReset() {
    _loadingProgressResetTimer?.cancel();
    _loadingProgressResetTimer = Timer(
      const Duration(milliseconds: 1600),
      () {
        _loadingMonitorStages = const [];
        notifyListeners();
      },
    );
  }

  List<String> _buildLoadingSteps() {
    return <String>[
      'Starting TrendPulse for ${_selectedSourceLabels()}',
      'Sending collected records to $_defaultLlmModel in ${_outputLanguageLabel()}',
      'Receiving the model result and updating the dashboard',
    ];
  }

  String _selectedSourceLabels() {
    final labels = _selectedSources.map((source) {
      return switch (source) {
        SourcePlatform.reddit => 'REDDIT',
        SourcePlatform.youtube => 'YOUTUBE',
        SourcePlatform.x => 'X',
      };
    }).toList()
      ..sort();
    return labels.join(', ');
  }

  String _outputLanguageLabel() {
    return _outputLanguage == AppLanguage.chinese ? 'Chinese' : 'English';
  }

  int _resolveLoadingStepIndex(List<MonitorStage> stages) {
    final stageNames = stages.map((stage) => stage.stage).toSet();
    if (stageNames.contains('response_ready')) {
      return 2;
    }
    if (stageNames.contains('llm_analysis_started')) {
      return 1;
    }
    return 0;
  }

  void _startMonitoringCountdownTicker() {
    _monitoringCountdownTimer?.cancel();
    if (!_monitoringEnabled) {
      return;
    }
    _monitoringCountdownTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) {
        if (!_monitoringEnabled) {
          _monitoringCountdownTimer?.cancel();
          _monitoringCountdownTimer = null;
          return;
        }
        notifyListeners();
      },
    );
  }

  void _scheduleNextMonitoringTrigger(Duration delay) {
    _monitoringTimer?.cancel();
    if (!_monitoringEnabled) {
      return;
    }
    _nextMonitoringTriggerAt = DateTime.now().add(delay);
    _monitoringTimer = Timer(delay, _handleMonitoringTrigger);
  }

  void _stopMonitoring() {
    _monitoringEnabled = false;
    _monitoringTimer?.cancel();
    _monitoringTimer = null;
    _monitoringCountdownTimer?.cancel();
    _monitoringCountdownTimer = null;
    _monitoringStartedAt = null;
    _nextMonitoringTriggerAt = null;
    _monitoringTriggerCount = 0;
  }

  void _handleMonitoringTrigger() {
    if (!_monitoringEnabled) {
      return;
    }
    if (_isLoading) {
      _scheduleNextMonitoringTrigger(const Duration(seconds: 5));
      notifyListeners();
      return;
    }
    _monitoringTriggerCount += 1;
    _nextMonitoringTriggerAt = null;
    notifyListeners();
    unawaited(_runMonitoringFetch());
  }

  Future<void> _runMonitoringFetch() async {
    try {
      await fetchDashboard(
        keyword: _currentKeyword,
        triggeredByMonitoring: true,
      );
    } finally {
      if (_monitoringEnabled) {
        _scheduleNextMonitoringTrigger(_monitoringInterval);
        notifyListeners();
      }
    }
  }
}
