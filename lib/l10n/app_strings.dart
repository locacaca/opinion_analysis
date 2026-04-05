import '../providers/app_language_provider.dart';

class AppStrings {
  const AppStrings._();

  static String dashboardTitle(AppLanguage language) {
    return 'TrendPulse';
  }

  static String dashboardSubtitle(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '跨社交平台的实时舆情洞察'
        : 'Live opinion intelligence across social channels';
  }

  static String refresh(AppLanguage language) {
    return language == AppLanguage.chinese ? '刷新' : 'Refresh';
  }

  static String syncing(AppLanguage language) {
    return language == AppLanguage.chinese ? '同步中' : 'Syncing';
  }

  static String analyze(AppLanguage language) {
    return language == AppLanguage.chinese ? '分析' : 'Analyze';
  }

  static String sourceSelector(AppLanguage language) {
    return language == AppLanguage.chinese ? '采集来源' : 'Sources';
  }

  static String sourceHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '只抓取勾选的网站内容'
        : 'Only crawl content from checked sources';
  }

  static String totalFetchLimit(AppLanguage language) {
    return language == AppLanguage.chinese ? '总抓取条数' : 'Total Fetch Limit';
  }

  static String totalFetchLimitHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '总量上限 50，按平台权重分配'
        : 'Up to 50 total items. Selected sources share this total by weight.';
  }

  static String sourceWeight(AppLanguage language) {
    return language == AppLanguage.chinese ? '平台权重' : 'Source Weight';
  }

  static String youtubeMode(AppLanguage language) {
    return language == AppLanguage.chinese ? 'YouTube 抓取方式' : 'YouTube Mode';
  }

  static String youtubeModeHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '官方 API 更快，浏览器增强模式更适合补字幕。'
        : 'Official API is faster. Browser mode is better when subtitle coverage matters.';
  }

  static String youtubeModeOfficial(AppLanguage language) {
    return language == AppLanguage.chinese ? '官方 API' : 'Official API';
  }

  static String youtubeModeBrowser(AppLanguage language) {
    return language == AppLanguage.chinese ? '浏览器增强' : 'Browser Enhanced';
  }

  static String weightLow(AppLanguage language) {
    return language == AppLanguage.chinese ? '低' : 'Low';
  }

  static String weightMedium(AppLanguage language) {
    return language == AppLanguage.chinese ? '中' : 'Medium';
  }

  static String weightHigh(AppLanguage language) {
    return language == AppLanguage.chinese ? '高' : 'High';
  }

  static String searchHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '输入关键词，例如 DeepSeek'
        : 'Enter a keyword, for example DeepSeek';
  }

  static String currentKeyword(AppLanguage language) {
    return language == AppLanguage.chinese ? '当前关键词' : 'Current Keyword';
  }

  static String executiveSummary(AppLanguage language) {
    return language == AppLanguage.chinese ? '摘要总览' : 'Executive Summary';
  }

  static String sentimentIndex(AppLanguage language) {
    return language == AppLanguage.chinese ? '情感指数' : 'Sentiment Index';
  }

  static String heatIndex(AppLanguage language) {
    return language == AppLanguage.chinese ? '热度指数' : 'Heat Index';
  }

  static String sourceCoverage(AppLanguage language) {
    return language == AppLanguage.chinese ? '来源覆盖' : 'Source Coverage';
  }

  static String signalStrength(AppLanguage language) {
    return language == AppLanguage.chinese ? '信号强度' : 'signal strength';
  }

  static String coreControversies(AppLanguage language) {
    return language == AppLanguage.chinese ? '核心争议点' : 'Core Controversies';
  }

  static String rawPosts(AppLanguage language) {
    return language == AppLanguage.chinese ? '源数据流' : 'Raw Posts';
  }

  static String rawPostsPageTitle(AppLanguage language) {
    return language == AppLanguage.chinese ? '源数据流' : 'Raw Posts';
  }

  static String postsCount(AppLanguage language, int count) {
    return language == AppLanguage.chinese ? '$count 条' : '$count posts';
  }

  static String viewAll(AppLanguage language, int count) {
    return language == AppLanguage.chinese ? '查看全部 ($count)' : 'View All ($count)';
  }

  static String openSourcePost(AppLanguage language) {
    return language == AppLanguage.chinese ? '打开原文' : 'Open source post';
  }

  static String languageToggle(AppLanguage language) {
    return language == AppLanguage.chinese ? 'EN' : '中文';
  }

  static String interfaceLanguage(AppLanguage language) {
    return language == AppLanguage.chinese ? '界面语言' : 'Interface Language';
  }

  static String outputLanguage(AppLanguage language) {
    return language == AppLanguage.chinese ? '输出语言' : 'Output Language';
  }

  static String outputLanguageHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '该选项会直接告诉大模型使用哪种语言输出摘要与争议点。'
        : 'This tells the model which language to use for the summary and discussion points.';
  }

  static String monitoring(AppLanguage language) {
    return language == AppLanguage.chinese ? '监控' : 'Monitoring';
  }

  static String monitoringHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '开启后会按设定间隔自动重新运行一次完整流程。'
        : 'When enabled, TrendPulse reruns the full workflow at the selected interval.';
  }

  static String monitoringInterval(AppLanguage language) {
    return language == AppLanguage.chinese ? '监控间隔' : 'Monitoring Interval';
  }

  static String monitoringStart(AppLanguage language) {
    return language == AppLanguage.chinese ? '开启监控' : 'Start Monitoring';
  }

  static String monitoringStop(AppLanguage language) {
    return language == AppLanguage.chinese ? '关闭监控' : 'Stop Monitoring';
  }

  static String monitoringLocked(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '监控开启后，关键词、平台、平台权重、抓取数量、输出语言和监控间隔都会被锁定。'
        : 'All analysis settings are locked while monitoring is enabled.';
  }

  static String sourceUnavailable(AppLanguage language) {
    return language == AppLanguage.chinese ? '暂未开放' : 'Not Available Yet';
  }

  static String monitoringAlertTitle(AppLanguage language) {
    return language == AppLanguage.chinese ? '舆情预警' : 'Opinion Alert';
  }

  static String monitoringAlertBody(AppLanguage language, String keyword, int score) {
    return language == AppLanguage.chinese
        ? '关键词“$keyword”的舆情分数已降至 $score，低于预警阈值 30。'
        : 'The sentiment score for "$keyword" has dropped to $score, below the alert threshold of 30.';
  }

  static String languageEnglish(AppLanguage language) {
    return language == AppLanguage.chinese ? '英文' : 'English';
  }

  static String languageChinese(AppLanguage language) {
    return language == AppLanguage.chinese ? '中文' : 'Chinese';
  }

  static String retainedCount(AppLanguage language, int count) {
    return language == AppLanguage.chinese ? '有效内容 $count' : '$count retained';
  }

  static String noPosts(AppLanguage language) {
    return language == AppLanguage.chinese ? '暂无源数据' : 'No source posts available';
  }

  static String sourceLabel(AppLanguage language, String source, int count) {
    if (language == AppLanguage.chinese) {
      return '$source $count';
    }
    return '$source $count';
  }

  static String sentimentLabel(AppLanguage language, int score) {
    if (language == AppLanguage.chinese) {
      if (score >= 75) {
        return '高度正向';
      }
      if (score >= 55) {
        return '偏正向';
      }
      if (score >= 45) {
        return '中性';
      }
      if (score >= 25) {
        return '偏负向';
      }
      return '高度负向';
    }

    if (score >= 75) {
      return 'Strongly Positive';
    }
    if (score >= 55) {
      return 'Leaning Positive';
    }
    if (score >= 45) {
      return 'Neutral';
    }
    if (score >= 25) {
      return 'Leaning Negative';
    }
    return 'Strongly Negative';
  }

  static String copy(AppLanguage language) {
    return language == AppLanguage.chinese ? '复制' : 'Copy';
  }

  static String copyAll(AppLanguage language) {
    return language == AppLanguage.chinese ? '全部复制' : 'Copy All';
  }

  static String copied(AppLanguage language) {
    return language == AppLanguage.chinese ? '已复制到剪贴板' : 'Copied to clipboard';
  }

  static String noControversies(AppLanguage language) {
    return language == AppLanguage.chinese ? '暂无争议点' : 'No controversy points available';
  }

  static String inputPromptTitle(AppLanguage language) {
    return language == AppLanguage.chinese ? '输入关键词开始分析' : 'Enter a keyword to start analysis';
  }

  static String inputPromptBody(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '当前不会自动请求数据。请输入关键词并点击“分析”，系统才会开始抓取、入库和分析流程。'
        : 'No request is sent automatically. Enter a keyword and tap Analyze to start collection, storage, and analysis.';
  }

  static String loadingBody(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '正在抓取数据、写入数据库并调用模型分析，请稍候。'
        : 'Collecting data, storing records, and running model analysis. Please wait.';
  }

  static String liveProgress(AppLanguage language) {
    return language == AppLanguage.chinese ? '当前进度' : 'Live Progress';
  }

  static String liveProgressHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '进度会根据后端真实阶段更新：启动、送入大模型、返回结果。'
        : 'This progress follows the real backend stages: start, send to model, and return result.';
  }

  static String backendTimeline(AppLanguage language) {
    return language == AppLanguage.chinese ? '后端执行时间线' : 'Backend Timeline';
  }

  static String backendTimelineHint(AppLanguage language) {
    return language == AppLanguage.chinese
        ? '以下为后端本次真实执行过的主要阶段。'
        : 'These are the actual backend stages completed in this run.';
  }
}
