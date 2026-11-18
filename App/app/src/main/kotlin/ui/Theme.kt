package com.tally.app.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Colour never carries a score or status.
private val Ink = Color(0xFF26372C)
private val Paper = Color(0xFFF5F1E8)
private val Oat = Color(0xFFD9C9A8)
private val Clay = Color(0xFF995438)
private val White = Color(0xFFFFFFFF)

// Error roles use the same palette as the other controls.
private val lightColors = lightColorScheme(
    primary = Ink, onPrimary = White, primaryContainer = Oat, onPrimaryContainer = Ink,
    inversePrimary = Oat,
    secondary = Ink, onSecondary = White, secondaryContainer = Oat, onSecondaryContainer = Ink,
    tertiary = Clay, onTertiary = White, tertiaryContainer = Oat, onTertiaryContainer = Ink,
    background = Paper, onBackground = Ink,
    surface = Paper, onSurface = Ink, surfaceVariant = Oat, onSurfaceVariant = Ink,
    surfaceTint = Ink, inverseSurface = Ink, inverseOnSurface = White,
    error = Ink, onError = White, errorContainer = Oat, onErrorContainer = Ink,
    outline = Ink, outlineVariant = Color(0xFFD4D1C6), scrim = Ink,
    surfaceBright = Paper, surfaceDim = Oat,
    surfaceContainerLowest = White, surfaceContainerLow = White, surfaceContainer = White,
    surfaceContainerHigh = Oat, surfaceContainerHighest = Oat,
)

private val DarkSurface = Color(0xFF18231C)
private val DarkContainer = Color(0xFF243128)
private val DarkAccentContainer = Color(0xFF4C5140)
private val DarkOutline = Color(0xFFA7B1A2)

private val darkColors = darkColorScheme(
    primary = Oat, onPrimary = Ink, primaryContainer = DarkAccentContainer, onPrimaryContainer = Paper,
    inversePrimary = Ink,
    secondary = Oat, onSecondary = Ink, secondaryContainer = DarkAccentContainer, onSecondaryContainer = Paper,
    tertiary = Color(0xFFE6AA91), onTertiary = Ink, tertiaryContainer = DarkAccentContainer, onTertiaryContainer = Paper,
    background = DarkSurface, onBackground = Paper,
    surface = DarkSurface, onSurface = Paper, surfaceVariant = DarkAccentContainer, onSurfaceVariant = Paper,
    surfaceTint = Oat, inverseSurface = Paper, inverseOnSurface = Ink,
    error = Oat, onError = Ink, errorContainer = DarkAccentContainer, onErrorContainer = Paper,
    outline = DarkOutline, outlineVariant = Color(0xFF424E44), scrim = Color.Black,
    surfaceBright = Color(0xFF344639), surfaceDim = DarkSurface,
    surfaceContainerLowest = Color(0xFF141C16), surfaceContainerLow = DarkSurface,
    surfaceContainer = DarkContainer, surfaceContainerHigh = Color(0xFF2B3A2F),
    surfaceContainerHighest = Color(0xFF334336),
)

// Atkinson Hyperlegible is not in the workspace, so this is the system sans (open item in docs/UI-REPORT.md).
private val Sans = FontFamily.SansSerif
private fun style(size: Int, line: Int, bold: Boolean = false, tracking: Double = 0.0) = TextStyle(
    fontFamily = Sans, fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
    fontSize = size.sp, lineHeight = line.sp, letterSpacing = tracking.sp, color = Color.Unspecified,
)

private val type = Typography(
    displayLarge = style(57, 64, bold = true, tracking = -0.25),
    displayMedium = style(45, 52, bold = true),
    displaySmall = style(36, 44, bold = true),
    headlineLarge = style(32, 40, bold = true),
    headlineMedium = style(28, 36, bold = true),
    headlineSmall = style(24, 32, bold = true),
    titleLarge = style(22, 28, bold = true),
    titleMedium = style(18, 24, bold = true),
    titleSmall = style(16, 22, bold = true),
    bodyLarge = style(18, 26),
    bodyMedium = style(16, 24),
    bodySmall = style(14, 20),
    labelLarge = style(16, 20, bold = true),
    labelMedium = style(13, 16, bold = true, tracking = 1.2),
    labelSmall = style(12, 16, bold = true, tracking = 1.0),
)

private val shapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(36.dp),
)

@Composable
fun TallyTheme(darkMode: Boolean = false, content: @Composable () -> Unit) =
    MaterialTheme(colorScheme = if (darkMode) darkColors else lightColors, typography = type, shapes = shapes, content = content)
