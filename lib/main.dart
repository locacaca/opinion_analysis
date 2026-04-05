import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';

import 'providers/app_language_provider.dart';
import 'providers/sentiment_provider.dart';
import 'screens/dashboard_page.dart';
import 'services/sentiment_api_service.dart';

void main() {
  runApp(const TrendPulseApp());
}

class TrendPulseApp extends StatelessWidget {
  const TrendPulseApp({super.key});

  @override
  Widget build(BuildContext context) {
    final baseTheme = ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme.fromSeed(
        seedColor: const Color(0xFF00C2FF),
        brightness: Brightness.dark,
      ).copyWith(
        primary: const Color(0xFF4DE2C5),
        secondary: const Color(0xFF00C2FF),
        surface: const Color(0xFF0F172A),
        surfaceContainerHighest: const Color(0xFF162033),
      ),
      scaffoldBackgroundColor: const Color(0xFF07111F),
    );

    return MultiProvider(
      providers: [
        ChangeNotifierProvider<AppLanguageProvider>(
          create: (_) => AppLanguageProvider(),
        ),
        ChangeNotifierProvider<SentimentProvider>(
          create: (_) => SentimentProvider(
            apiService: SentimentApiService(),
          ),
        ),
      ],
      child: MaterialApp(
        title: 'TrendPulse',
        debugShowCheckedModeBanner: false,
        theme: baseTheme.copyWith(
          textTheme: GoogleFonts.spaceGroteskTextTheme(baseTheme.textTheme),
          appBarTheme: AppBarTheme(
            centerTitle: false,
            backgroundColor: Colors.transparent,
            elevation: 0,
            foregroundColor: Colors.white,
            titleTextStyle: GoogleFonts.orbitron(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: Colors.white,
              letterSpacing: 1.2,
            ),
          ),
          cardTheme: CardThemeData(
            color: const Color(0xFF101B2D).withValues(alpha: 0.88),
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(28),
              side: BorderSide(
                color: Colors.white.withValues(alpha: 0.08),
              ),
            ),
          ),
        ),
        home: const DashboardPage(),
      ),
    );
  }
}
