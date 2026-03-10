import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

// ─── Dfacto Monochrome Color System ──────────────────────────────────────────
class DfactoColors {
  DfactoColors._();

  // ── Dark Mode ──────────────────────────────────────────────────────────────
  static const Color darkBackground    = Color(0xFF0A0A0A); // near-black
  static const Color darkSurface       = Color(0xFF141414); // elevated surface
  static const Color darkSurfaceHigh   = Color(0xFF1F1F1F); // higher elevation
  static const Color darkBorder        = Color(0xFF2A2A2A); // subtle divider
  static const Color darkBorderStrong  = Color(0xFF404040); // stronger border
  static const Color darkTextPrimary   = Color(0xFFF5F5F5); // near-white text
  static const Color darkTextSecondary = Color(0xFFA0A0A0); // muted text
  static const Color darkTextMuted     = Color(0xFF606060); // very muted text
  static const Color darkAccent        = Color(0xFFFFFFFF); // white accent
  static const Color darkAccentSoft    = Color(0x22FFFFFF); // white glow

  // ── Light Mode ─────────────────────────────────────────────────────────────
  static const Color lightBackground    = Color(0xFFFAFAFA); // off-white
  static const Color lightSurface       = Color(0xFFFFFFFF); // pure white card
  static const Color lightSurfaceHigh   = Color(0xFFF0F0F0); // subtle elevation
  static const Color lightBorder        = Color(0xFFE0E0E0); // divider
  static const Color lightBorderStrong  = Color(0xFFC0C0C0); // stronger border
  static const Color lightTextPrimary   = Color(0xFF0A0A0A); // near-black text
  static const Color lightTextSecondary = Color(0xFF606060); // muted text
  static const Color lightTextMuted     = Color(0xFFA0A0A0); // very muted text
  static const Color lightAccent        = Color(0xFF000000); // black accent
  static const Color lightAccentSoft    = Color(0x14000000); // black glow

  // ── Semantic Verdict Colors (matching UI/UX prototype) ────────────────────
  static const Color verdictTrue    = Color(0xFF48D67B); // prototype green
  static const Color verdictFalse   = Color(0xFFFF5353); // prototype red
  static const Color verdictMixed   = Color(0xFFFFCC52); // prototype yellow
  static const Color verdictUnknown = Color(0xFF9E9E9E); // gray
}

// ─── Glass Morphism Colors ────────────────────────────────────────────────────
class GlassColors {
  GlassColors._();
  static const Color surface      = Color(0x38FFFFFF); // rgba(255,255,255,0.22)
  static const Color surfaceHeavy = Color(0x8CFFFFFF); // rgba(255,255,255,0.55)
  static const Color border       = Color(0x14FFFFFF); // rgba(255,255,255,0.08)
  static const Color navBg        = Color(0x1FFFFFFF); // rgba(255,255,255,0.12)
  static const Color navBorder    = Color(0x4DFFFFFF); // rgba(255,255,255,0.30)
}

// ─── Context-Aware Color Extensions ──────────────────────────────────────────
extension DfactoThemeExtension on BuildContext {
  bool get isDark => Theme.of(this).brightness == Brightness.dark;

  Color get bg            => isDark ? DfactoColors.darkBackground    : DfactoColors.lightBackground;
  Color get surface       => isDark ? DfactoColors.darkSurface       : DfactoColors.lightSurface;
  Color get surfaceHigh   => isDark ? DfactoColors.darkSurfaceHigh   : DfactoColors.lightSurfaceHigh;
  Color get border        => isDark ? DfactoColors.darkBorder        : DfactoColors.lightBorder;
  Color get borderStrong  => isDark ? DfactoColors.darkBorderStrong  : DfactoColors.lightBorderStrong;
  Color get textPrimary   => isDark ? DfactoColors.darkTextPrimary   : DfactoColors.lightTextPrimary;
  Color get textSecondary => isDark ? DfactoColors.darkTextSecondary : DfactoColors.lightTextSecondary;
  Color get textMuted     => isDark ? DfactoColors.darkTextMuted     : DfactoColors.lightTextMuted;
  Color get accent        => isDark ? DfactoColors.darkAccent        : DfactoColors.lightAccent;
  Color get accentSoft    => isDark ? DfactoColors.darkAccentSoft    : DfactoColors.lightAccentSoft;
}

// ─── Typography ───────────────────────────────────────────────────────────────
class DfactoTextStyles {
  DfactoTextStyles._();

  static TextStyle displayLarge(Color color) => GoogleFonts.outfit(
    fontSize: 26,
    fontWeight: FontWeight.w700,
    color: color,
    letterSpacing: -0.5,
  );

  static TextStyle headlineMedium(Color color) => GoogleFonts.outfit(
    fontSize: 18,
    fontWeight: FontWeight.w600,
    color: color,
    letterSpacing: -0.3,
  );

  static TextStyle bodyMedium(Color color) => GoogleFonts.inter(
    fontSize: 13,
    fontWeight: FontWeight.w400,
    color: color,
    height: 1.55,
  );

  static TextStyle bodySmall(Color color) => GoogleFonts.inter(
    fontSize: 11,
    fontWeight: FontWeight.w400,
    color: color,
    height: 1.4,
  );

  static TextStyle labelBold(Color color) => GoogleFonts.outfit(
    fontSize: 10,
    fontWeight: FontWeight.w700,
    color: color,
    letterSpacing: 1.0,
  );
}

// ─── Theme Data ───────────────────────────────────────────────────────────────
class AppTheme {
  AppTheme._();

  static ThemeData get dark => _build(
    brightness: Brightness.dark,
    background: DfactoColors.darkBackground,
    surface: DfactoColors.darkSurface,
    surfaceHigh: DfactoColors.darkSurfaceHigh,
    border: DfactoColors.darkBorder,
    textPrimary: DfactoColors.darkTextPrimary,
    textSecondary: DfactoColors.darkTextSecondary,
    textMuted: DfactoColors.darkTextMuted,
    accent: DfactoColors.darkAccent,
    accentSoft: DfactoColors.darkAccentSoft,
  );

  static ThemeData get light => _build(
    brightness: Brightness.light,
    background: DfactoColors.lightBackground,
    surface: DfactoColors.lightSurface,
    surfaceHigh: DfactoColors.lightSurfaceHigh,
    border: DfactoColors.lightBorder,
    textPrimary: DfactoColors.lightTextPrimary,
    textSecondary: DfactoColors.lightTextSecondary,
    textMuted: DfactoColors.lightTextMuted,
    accent: DfactoColors.lightAccent,
    accentSoft: DfactoColors.lightAccentSoft,
  );

  static ThemeData _build({
    required Brightness brightness,
    required Color background,
    required Color surface,
    required Color surfaceHigh,
    required Color border,
    required Color textPrimary,
    required Color textSecondary,
    required Color textMuted,
    required Color accent,
    required Color accentSoft,
  }) {
    return ThemeData(
      brightness: brightness,
      scaffoldBackgroundColor: background,
      colorScheme: ColorScheme(
        brightness: brightness,
        primary: accent,
        onPrimary: brightness == Brightness.dark ? Colors.black : Colors.white,
        secondary: textSecondary,
        onSecondary: background,
        error: DfactoColors.verdictFalse,
        onError: Colors.white,
        surface: surface,
        onSurface: textPrimary,
      ),
      textTheme: TextTheme(
        displayLarge: DfactoTextStyles.displayLarge(textPrimary),
        headlineMedium: DfactoTextStyles.headlineMedium(textPrimary),
        bodyMedium: DfactoTextStyles.bodyMedium(textSecondary),
        bodySmall: DfactoTextStyles.bodySmall(textMuted),
        labelSmall: DfactoTextStyles.labelBold(textPrimary),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: surface,
        indicatorColor: accentSoft,
        surfaceTintColor: Colors.transparent,
        shadowColor: Colors.transparent,
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return DfactoTextStyles.labelBold(accent).copyWith(fontSize: 10);
          }
          return DfactoTextStyles.labelBold(textMuted).copyWith(fontSize: 10);
        }),
        iconTheme: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.selected)) {
            return IconThemeData(color: accent, size: 22);
          }
          return IconThemeData(color: textMuted, size: 22);
        }),
      ),
      cardTheme: CardTheme(
        color: surfaceHigh,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: border, width: 1),
        ),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      ),
      dividerColor: border,
      useMaterial3: true,
    );
  }
}
