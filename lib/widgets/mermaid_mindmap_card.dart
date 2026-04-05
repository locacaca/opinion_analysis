import 'package:flutter/material.dart';

import '../models/sentiment_models.dart';
import '../providers/app_language_provider.dart';
import '../services/mermaid_mindmap_builder.dart';

class MermaidMindmapCard extends StatelessWidget {
  const MermaidMindmapCard({
    super.key,
    required this.dashboard,
    required this.language,
  });

  final DashboardResponse dashboard;
  final AppLanguage language;

  @override
  Widget build(BuildContext context) {
    final document = MermaidMindmapBuilder.build(
      dashboard: dashboard,
      language: language,
    );

    return Card(
      clipBehavior: Clip.antiAlias,
      child: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [
              const Color(0xFF0F1C32).withValues(alpha: 0.96),
              const Color(0xFF142945).withValues(alpha: 0.92),
              const Color(0xFF0C1527).withValues(alpha: 0.98),
            ],
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Mermaid Mind Map',
                          style:
                              Theme.of(context).textTheme.titleLarge?.copyWith(
                                    color: Colors.white,
                                    fontWeight: FontWeight.w800,
                                  ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Auto-generated from the summary, core views, and signals.',
                          style:
                              Theme.of(context).textTheme.bodySmall?.copyWith(
                                    color: Colors.white70,
                                    height: 1.5,
                                  ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _MindmapCanvas(
                rootLabel: document.rootLabel,
                branches: document.branches,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _MindmapCanvas extends StatelessWidget {
  const _MindmapCanvas({
    required this.rootLabel,
    required this.branches,
  });

  final String rootLabel;
  final List<MermaidMindmapBranch> branches;

  @override
  Widget build(BuildContext context) {
    final branchColors = <Color>[
      const Color(0xFF53E0C1),
      const Color(0xFF53B7FF),
      const Color(0xFFFFB85C),
    ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(24),
        border: Border.all(
          color: Colors.white.withValues(alpha: 0.08),
        ),
        color: Colors.white.withValues(alpha: 0.03),
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              gradient: const LinearGradient(
                colors: [
                  Color(0xFF57E6C0),
                  Color(0xFF4CA7FF),
                ],
              ),
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFF4CA7FF).withValues(alpha: 0.25),
                  blurRadius: 20,
                  spreadRadius: 2,
                ),
              ],
            ),
            child: Column(
              children: [
                Text(
                  'Topic',
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                        color: const Color(0xFF072033),
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.8,
                      ),
                ),
                const SizedBox(height: 4),
                Text(
                  rootLabel,
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        color: const Color(0xFF04131F),
                        fontWeight: FontWeight.w900,
                      ),
                ),
              ],
            ),
          ),
          Container(
            width: 2,
            height: 28,
            margin: const EdgeInsets.symmetric(vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(999),
            ),
          ),
          Wrap(
            spacing: 14,
            runSpacing: 14,
            alignment: WrapAlignment.center,
            children: [
              for (var index = 0; index < branches.length; index++)
                _MindmapBranchCard(
                  branch: branches[index],
                  accent: branchColors[index % branchColors.length],
                ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MindmapBranchCard extends StatelessWidget {
  const _MindmapBranchCard({
    required this.branch,
    required this.accent,
  });

  final MermaidMindmapBranch branch;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return ConstrainedBox(
      constraints: const BoxConstraints(
        minWidth: 240,
        maxWidth: 320,
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(22),
          color: accent.withValues(alpha: 0.09),
          border: Border.all(
            color: accent.withValues(alpha: 0.34),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 12,
                  height: 12,
                  decoration: BoxDecoration(
                    color: accent,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: accent.withValues(alpha: 0.35),
                        blurRadius: 10,
                        spreadRadius: 1,
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: Text(
                    branch.title,
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          color: Colors.white,
                          fontWeight: FontWeight.w800,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 14),
            ...branch.nodes.map(
              (node) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _MindmapNodeTile(
                  node: node,
                  accent: accent,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _MindmapNodeTile extends StatelessWidget {
  const _MindmapNodeTile({
    required this.node,
    required this.accent,
  });

  final MermaidMindmapNode node;
  final Color accent;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.04),
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 8,
                height: 8,
                margin: const EdgeInsets.only(top: 6),
                decoration: BoxDecoration(
                  color: accent,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  node.title,
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w700,
                        height: 1.4,
                      ),
                ),
              ),
            ],
          ),
          if (node.details.isNotEmpty) ...[
            const SizedBox(height: 10),
            ...node.details.map(
              (detail) => Padding(
                padding: const EdgeInsets.only(left: 18, bottom: 6),
                child: Text(
                  '- $detail',
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.white70,
                        height: 1.45,
                      ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
