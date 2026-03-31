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
}
