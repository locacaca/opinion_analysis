import '../models/sentiment_models.dart';
import '../providers/app_language_provider.dart';

class MermaidMindmapDocument {
  const MermaidMindmapDocument({
    required this.rootLabel,
    required this.mermaid,
    required this.branches,
  });

  final String rootLabel;
  final String mermaid;
  final List<MermaidMindmapBranch> branches;
}

class MermaidMindmapBranch {
  const MermaidMindmapBranch({
    required this.title,
    required this.nodes,
  });

  final String title;
  final List<MermaidMindmapNode> nodes;
}

class MermaidMindmapNode {
  const MermaidMindmapNode({
    required this.title,
    this.details = const [],
  });

  final String title;
  final List<String> details;
}

class MermaidMindmapBuilder {
  const MermaidMindmapBuilder._();

  static MermaidMindmapDocument build({
    required DashboardResponse dashboard,
    required AppLanguage language,
  }) {
    final summaryNodes = _splitSummary(
      dashboard.summary,
      fallback: 'No summary available',
    );
    final signalNodes = <MermaidMindmapNode>[
      MermaidMindmapNode(title: 'Sentiment ${dashboard.sentimentScore}/100'),
      MermaidMindmapNode(title: 'Heat ${dashboard.heatScore}/100'),
      MermaidMindmapNode(title: 'Retained ${dashboard.retainedCommentCount}'),
      ...dashboard.sourceBreakdown.entries
          .where((entry) => entry.value > 0)
          .map(
            (entry) => MermaidMindmapNode(
              title: '${entry.key.toUpperCase()} ${entry.value}',
            ),
          ),
    ];
    final controversyNodes = dashboard.controversyPoints.isEmpty
        ? const <MermaidMindmapNode>[
            MermaidMindmapNode(title: 'No controversy points'),
          ]
        : dashboard.controversyPoints.take(3).map((point) {
            return MermaidMindmapNode(
              title: point.title,
              details: _splitSummary(
                point.summary,
                fallback: 'No additional detail',
                maxSegments: 3,
              ),
            );
          }).toList();

    final branches = <MermaidMindmapBranch>[
      MermaidMindmapBranch(
        title: 'Summary',
        nodes: summaryNodes.map((item) => MermaidMindmapNode(title: item)).toList(),
      ),
      MermaidMindmapBranch(
        title: 'Signals',
        nodes: signalNodes,
      ),
      MermaidMindmapBranch(
        title: 'Core Views',
        nodes: controversyNodes,
      ),
    ];

    return MermaidMindmapDocument(
      rootLabel: dashboard.keyword,
      mermaid: _buildMermaidText(
        keyword: dashboard.keyword,
        branches: branches,
      ),
      branches: branches,
    );
  }

  static List<String> _splitSummary(
    String rawText, {
    required String fallback,
    int maxSegments = 4,
  }) {
    final normalized = rawText.trim();
    if (normalized.isEmpty) {
      return <String>[fallback];
    }

    final pieces = normalized
        .split(RegExp(r'[.!?;\n]+'))
        .map((item) => item.trim())
        .where((item) => item.isNotEmpty)
        .toList();
    if (pieces.isEmpty) {
      return <String>[normalized];
    }
    return pieces.take(maxSegments).toList();
  }

  static String _buildMermaidText({
    required String keyword,
    required List<MermaidMindmapBranch> branches,
  }) {
    final buffer = StringBuffer();
    buffer.writeln('mindmap');
    buffer.writeln('  root((${_sanitize(keyword)}))');
    for (final branch in branches) {
      buffer.writeln('    ${_sanitize(branch.title)}');
      for (final node in branch.nodes) {
        buffer.writeln('      ${_sanitize(node.title)}');
        for (final detail in node.details) {
          buffer.writeln('        ${_sanitize(detail)}');
        }
      }
    }
    return buffer.toString().trimRight();
  }

  static String _sanitize(String value) {
    final normalized = value
        .replaceAll('\r', ' ')
        .replaceAll('\n', ' ')
        .replaceAll('"', "'")
        .replaceAll(':', ' - ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
    return normalized.isEmpty ? 'N/A' : normalized;
  }
}
