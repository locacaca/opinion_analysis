import '../providers/app_language_provider.dart';

class LocalInsightTranslator {
  const LocalInsightTranslator._();

  static final List<MapEntry<String, String>> _phraseMap = [
    const MapEntry('Dashboard request timed out after 570 seconds.', '仪表盘请求已在 570 秒后超时。'),
    const MapEntry('The backend is reachable, but collection or LLM analysis is taking too long.', '后端可以访问，但数据采集或模型分析耗时过长。'),
    const MapEntry('Failed to load dashboard data:', '加载仪表盘数据失败：'),
    const MapEntry('Backend is unreachable at', '后端无法连接：'),
    const MapEntry('SocketException:', '网络异常：'),
    const MapEntry('HTTP client failed to reach', 'HTTP 客户端无法访问'),
    const MapEntry('ClientException:', '客户端异常：'),
    const MapEntry('Backend returned', '后端返回'),
    const MapEntry('Collected', '本轮采集到'),
    const MapEntry('source records about', '条与'),
    const MapEntry('Overall discussion appears', '整体讨论呈现'),
    const MapEntry('with a weighted sentiment score of', '加权情感得分为'),
    const MapEntry('mostly positive', '整体偏正面'),
    const MapEntry('mostly negative', '整体偏负面'),
    const MapEntry('mixed', '观点较为分化'),
    const MapEntry('Core Theme', '核心讨论点'),
    const MapEntry('Synthesized from the full current collection round.', '基于当前轮次全部采集内容综合归纳。'),
    const MapEntry('weighted sentiment score', '加权情感得分'),
    const MapEntry('overall discussion', '整体讨论'),
    const MapEntry('pricing', '定价'),
    const MapEntry('price', '价格'),
    const MapEntry('cost', '成本'),
    const MapEntry('performance', '性能'),
    const MapEntry('quality', '质量'),
    const MapEntry('reliability', '稳定性'),
    const MapEntry('speed', '速度'),
    const MapEntry('privacy', '隐私'),
    const MapEntry('safety', '安全性'),
    const MapEntry('benchmark', '基准测试'),
    const MapEntry('deployment', '部署'),
    const MapEntry('open source', '开源'),
    const MapEntry('model', '模型'),
    const MapEntry('developer', '开发者'),
    const MapEntry('reasoning', '推理'),
    const MapEntry('coding', '代码能力'),
    const MapEntry('efficiency', '效率'),
    const MapEntry('latency', '延迟'),
    const MapEntry('accuracy', '准确性'),
    const MapEntry('hallucination', '幻觉问题'),
    const MapEntry('context window', '上下文窗口'),
    const MapEntry('training data', '训练数据'),
    const MapEntry('community', '社区'),
    const MapEntry('enterprise', '企业场景'),
    const MapEntry('consumer', '消费者场景'),
    const MapEntry('discussion', '讨论'),
    const MapEntry('theme', '主题'),
    const MapEntry('positive', '正面'),
    const MapEntry('negative', '负面'),
  ];

  static String translate(String text, AppLanguage language) {
    if (language != AppLanguage.chinese) {
      return text;
    }

    var translated = text.trim();
    if (translated.isEmpty) {
      return translated;
    }

    for (final entry in _phraseMap) {
      translated = translated.replaceAllMapped(
        RegExp(entry.key, caseSensitive: false),
        (_) => entry.value,
      );
    }

    translated = translated
        .replaceAll(' ,', '，')
        .replaceAll(', ', '，')
        .replaceAll(': ', '：')
        .replaceAll('. ', '。')
        .replaceAll('/100.', '/100。')
        .replaceAll('  ', ' ')
        .replaceAll(' 条与 ', ' 条与 ')
        .replaceAll(' 的 ', ' 的 ');

    if (!translated.endsWith('。') &&
        !translated.endsWith('！') &&
        !translated.endsWith('？') &&
        !translated.endsWith('.') &&
        !translated.endsWith(')')) {
      translated = '$translated。';
    }

    return translated;
  }
}
