import 'package:flutter/foundation.dart';

enum AppLanguage {
  english,
  chinese,
}

class AppLanguageProvider extends ChangeNotifier {
  AppLanguage _language = AppLanguage.english;

  AppLanguage get language => _language;
  bool get isChinese => _language == AppLanguage.chinese;

  void toggleLanguage() {
    _language = isChinese ? AppLanguage.english : AppLanguage.chinese;
    notifyListeners();
  }
}
