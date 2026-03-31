import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

import 'package:opinion_analysis/providers/app_language_provider.dart';
import 'package:opinion_analysis/providers/sentiment_provider.dart';
import 'package:opinion_analysis/screens/dashboard_page.dart';
import 'package:opinion_analysis/services/sentiment_api_service.dart';

void main() {
  testWidgets('dashboard renders keyword search and main sections',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
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
          theme: ThemeData(useMaterial3: true, brightness: Brightness.dark),
          home: const DashboardPage(),
        ),
      ),
    );

    await tester.pump();

    expect(find.text('TrendPulse'), findsOneWidget);
    expect(find.text('Sentiment Index'), findsOneWidget);
    expect(find.text('Heat Index'), findsOneWidget);
    expect(find.text('Core Controversies'), findsOneWidget);
    expect(find.byType(TextField), findsOneWidget);
  });
}
