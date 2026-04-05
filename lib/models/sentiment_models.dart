enum SourcePlatform {
  reddit,
  youtube,
  x,
}

enum SourceWeightTier {
  low,
  medium,
  high,
}

enum YouTubeCollectionMode {
  officialApi,
  headlessBrowser,
}

extension SourcePlatformValue on SourcePlatform {
  String get value => switch (this) {
        SourcePlatform.reddit => 'reddit',
        SourcePlatform.youtube => 'youtube',
        SourcePlatform.x => 'x',
      };

  String get displayName => switch (this) {
        SourcePlatform.reddit => 'REDDIT',
        SourcePlatform.youtube => 'YOUTUBE',
        SourcePlatform.x => 'X',
      };
}

extension SourceWeightTierValue on SourceWeightTier {
  String get value => switch (this) {
        SourceWeightTier.low => 'low',
        SourceWeightTier.medium => 'medium',
        SourceWeightTier.high => 'high',
      };

  int get weight => switch (this) {
        SourceWeightTier.low => 1,
        SourceWeightTier.medium => 2,
        SourceWeightTier.high => 3,
      };
}

extension YouTubeCollectionModeValue on YouTubeCollectionMode {
  String get value => switch (this) {
        YouTubeCollectionMode.officialApi => 'official_api',
        YouTubeCollectionMode.headlessBrowser => 'headless_browser',
      };
}

class DashboardResponse {
  const DashboardResponse({
    required this.keyword,
    required this.sentimentScore,
    required this.heatScore,
    required this.summary,
    required this.controversyPoints,
    required this.posts,
    required this.retainedCommentCount,
    required this.discardedCommentCount,
    required this.sourceBreakdown,
    this.sourceLimits = const {},
    this.rawCountBySource = const {},
    this.retainedCountBySource = const {},
    this.discardedCountBySource = const {},
    this.monitorStages = const [],
  });

  final String keyword;
  final int sentimentScore;
  final int heatScore;
  final String summary;
  final List<ControversyPoint> controversyPoints;
  final List<SourcePost> posts;
  final int retainedCommentCount;
  final int discardedCommentCount;
  final Map<String, int> sourceBreakdown;
  final Map<String, int> sourceLimits;
  final Map<String, int> rawCountBySource;
  final Map<String, int> retainedCountBySource;
  final Map<String, int> discardedCountBySource;
  final List<MonitorStage> monitorStages;

  factory DashboardResponse.fromJson(Map<String, dynamic> json) {
    final rawPoints =
        (json['controversy_points'] ?? json['controversyPoints'] ?? [])
            as List<dynamic>;
    final rawPosts =
        (json['posts'] ?? json['raw_posts'] ?? json['rawPosts'] ?? [])
            as List<dynamic>;
    final rawBreakdown = (json['source_breakdown'] ??
            json['sourceBreakdown'] ??
            <String, dynamic>{})
        as Map<String, dynamic>;
    final rawSourceLimits = (json['source_limits'] ??
            json['sourceLimits'] ??
            <String, dynamic>{})
        as Map<String, dynamic>;
    final rawRawCountBySource = (json['raw_count_by_source'] ??
            json['rawCountBySource'] ??
            <String, dynamic>{})
        as Map<String, dynamic>;
    final rawRetainedCountBySource = (json['retained_count_by_source'] ??
            json['retainedCountBySource'] ??
            <String, dynamic>{})
        as Map<String, dynamic>;
    final rawDiscardedCountBySource = (json['discarded_count_by_source'] ??
            json['discardedCountBySource'] ??
            <String, dynamic>{})
        as Map<String, dynamic>;
    final rawMonitor = (json['monitor'] ?? const <String, dynamic>{})
        as Map<String, dynamic>;
    final rawStages = (rawMonitor['stages'] ?? const <dynamic>[]) as List<dynamic>;

    return DashboardResponse(
      keyword: (json['keyword'] as String? ?? 'DeepSeek').trim(),
      sentimentScore: _clampScore(
        json['sentiment_score'] ?? json['sentimentScore'],
      ),
      heatScore: _clampScore(json['heat_score'] ?? json['heatScore']),
      summary: (json['summary'] as String? ?? 'No summary available.').trim(),
      controversyPoints: rawPoints
          .whereType<Map<String, dynamic>>()
          .map(ControversyPoint.fromJson)
          .toList(),
      posts: rawPosts
          .whereType<Map<String, dynamic>>()
          .map(SourcePost.fromJson)
          .toList(),
      retainedCommentCount:
          _toInt(json['retained_comment_count'] ?? json['retainedCommentCount']),
      discardedCommentCount: _toInt(
        json['discarded_comment_count'] ?? json['discardedCommentCount'],
      ),
      sourceBreakdown: rawBreakdown.map(
        (key, value) => MapEntry(key, _toInt(value)),
      ),
      sourceLimits: rawSourceLimits.map(
        (key, value) => MapEntry(key, _toInt(value)),
      ),
      rawCountBySource: rawRawCountBySource.map(
        (key, value) => MapEntry(key, _toInt(value)),
      ),
      retainedCountBySource: rawRetainedCountBySource.map(
        (key, value) => MapEntry(key, _toInt(value)),
      ),
      discardedCountBySource: rawDiscardedCountBySource.map(
        (key, value) => MapEntry(key, _toInt(value)),
      ),
      monitorStages: rawStages
          .whereType<Map<String, dynamic>>()
          .map(MonitorStage.fromJson)
          .toList(),
    );
  }

  DashboardResponse copyWith({
    String? keyword,
    int? sentimentScore,
    int? heatScore,
    String? summary,
    List<ControversyPoint>? controversyPoints,
    List<SourcePost>? posts,
    int? retainedCommentCount,
    int? discardedCommentCount,
    Map<String, int>? sourceBreakdown,
    Map<String, int>? sourceLimits,
    Map<String, int>? rawCountBySource,
    Map<String, int>? retainedCountBySource,
    Map<String, int>? discardedCountBySource,
    List<MonitorStage>? monitorStages,
  }) {
    return DashboardResponse(
      keyword: keyword ?? this.keyword,
      sentimentScore: sentimentScore ?? this.sentimentScore,
      heatScore: heatScore ?? this.heatScore,
      summary: summary ?? this.summary,
      controversyPoints: controversyPoints ?? this.controversyPoints,
      posts: posts ?? this.posts,
      retainedCommentCount: retainedCommentCount ?? this.retainedCommentCount,
      discardedCommentCount: discardedCommentCount ?? this.discardedCommentCount,
      sourceBreakdown: sourceBreakdown ?? this.sourceBreakdown,
      sourceLimits: sourceLimits ?? this.sourceLimits,
      rawCountBySource: rawCountBySource ?? this.rawCountBySource,
      retainedCountBySource:
          retainedCountBySource ?? this.retainedCountBySource,
      discardedCountBySource:
          discardedCountBySource ?? this.discardedCountBySource,
      monitorStages: monitorStages ?? this.monitorStages,
    );
  }

  static int _clampScore(dynamic rawValue) {
    final parsed = _toInt(rawValue, fallback: 50);
    return parsed.clamp(0, 100);
  }

  static int _toInt(dynamic rawValue, {int fallback = 0}) {
    return switch (rawValue) {
      int value => value,
      double value => value.round(),
      String value => int.tryParse(value) ?? fallback,
      _ => fallback,
    };
  }
}

class MonitorStage {
  const MonitorStage({
    required this.stage,
    required this.timestamp,
    required this.details,
  });

  final String stage;
  final String timestamp;
  final Map<String, dynamic> details;

  factory MonitorStage.fromJson(Map<String, dynamic> json) {
    return MonitorStage(
      stage: (json['stage'] as String? ?? '').trim(),
      timestamp: (json['timestamp'] as String? ?? '').trim(),
      details: ((json['details'] ?? const <String, dynamic>{})
              as Map<Object?, Object?>)
          .map(
        (key, value) => MapEntry(
          key?.toString() ?? '',
          value,
        ),
      ),
    );
  }
}

class ControversyPoint {
  const ControversyPoint({
    required this.title,
    required this.summary,
    this.link,
  });

  final String title;
  final String summary;
  final String? link;

  factory ControversyPoint.fromJson(Map<String, dynamic> json) {
    return ControversyPoint(
      title: (json['title'] as String? ?? 'Untitled').trim(),
      summary: (json['summary'] as String? ?? '').trim(),
      link: (json['link'] ?? json['url'] ?? json['original_link']) as String?,
    );
  }

  ControversyPoint copyWith({
    String? title,
    String? summary,
    String? link,
  }) {
    return ControversyPoint(
      title: title ?? this.title,
      summary: summary ?? this.summary,
      link: link ?? this.link,
    );
  }
}

class SourcePost {
  const SourcePost({
    required this.title,
    required this.content,
    required this.author,
    required this.originalLink,
    required this.source,
  });

  final String title;
  final String content;
  final String author;
  final String originalLink;
  final String source;

  factory SourcePost.fromJson(Map<String, dynamic> json) {
    final title =
        (json['title'] as String? ?? json['headline'] as String? ?? '').trim();
    final content = (json['content'] as String? ?? '').trim();
    return SourcePost(
      title: title.isEmpty ? content : title,
      content: content,
      author: (json['author'] as String? ?? 'Unknown').trim(),
      originalLink: (json['original_link'] ??
              json['originalLink'] ??
              json['link'] ??
              '') as String,
      source: (json['source'] as String? ?? 'social').trim(),
    );
  }
}
