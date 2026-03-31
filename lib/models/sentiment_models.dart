enum SourcePlatform {
  reddit,
  youtube,
  x,
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
