package com.jeevan.tally.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

// Fixed brand colors: wallpaper-derived dynamic colors must never replace this palette.
private val TallyColors = lightColorScheme(
    primary = Ink, onPrimary = Paper, primaryContainer = Oat, onPrimaryContainer = Ink,
    secondary = Clay, onSecondary = White, secondaryContainer = Color(0xFFE9E2D1), onSecondaryContainer = Ink,
    tertiary = Clay, onTertiary = White, tertiaryContainer = Oat, onTertiaryContainer = Ink,
    background = Paper, onBackground = Ink,
    surface = Paper, onSurface = Ink, surfaceVariant = White, onSurfaceVariant = Ink,
    surfaceContainerLowest = White, surfaceContainerLow = White,
    surfaceContainer = Color(0xFFEDE8DB), surfaceContainerHigh = Color(0xFFE6DFD0), surfaceContainerHighest = Oat,
    surfaceBright = White, surfaceDim = Oat, surfaceTint = Ink,
    outline = Color(0xFF797363), outlineVariant = Oat,
    inverseSurface = Ink, inverseOnSurface = Paper, inversePrimary = Paper,
    error = Clay, onError = White, errorContainer = Paper, onErrorContainer = Clay,
    scrim = Ink,
    primaryFixed = Paper, primaryFixedDim = Oat, onPrimaryFixed = Ink, onPrimaryFixedVariant = Ink,
    secondaryFixed = Paper, secondaryFixedDim = Oat, onSecondaryFixed = Clay, onSecondaryFixedVariant = Ink,
    tertiaryFixed = Paper, tertiaryFixedDim = Oat, onTertiaryFixed = Clay, onTertiaryFixedVariant = Ink,
)
private val TallyDarkColors = darkColorScheme(
    primary = Color(0xFFC2DBBF), onPrimary = Ink,
    primaryContainer = Color(0xFF304738), onPrimaryContainer = Color(0xFFE1F1DE),
    secondary = Oat, onSecondary = Color(0xFF332D20),
    secondaryContainer = Color(0xFF3D4032), onSecondaryContainer = Paper,
    tertiary = Color(0xFFFFB69B), onTertiary = Color(0xFF4B2515),
    background = Color(0xFF161C17), onBackground = Paper,
    surface = Color(0xFF161C17), onSurface = Paper,
    surfaceVariant = Color(0xFF3E483E), onSurfaceVariant = Color(0xFFCED5C8),
    surfaceContainerLowest = Color(0xFF111712), surfaceContainerLow = Color(0xFF1D251E),
    surfaceContainer = Color(0xFF252E26), surfaceContainerHigh = Color(0xFF303A31),
    surfaceContainerHighest = Color(0xFF3C483D),
    surfaceBright = Color(0xFF3C483D), surfaceDim = Color(0xFF161C17),
    outline = Color(0xFF9DA89A), outlineVariant = Color(0xFF505D50),
    error = Color(0xFFFFB4A5), onError = Color(0xFF541C11),
    errorContainer = Color(0xFF572A20), onErrorContainer = Color(0xFFFFDAD1),
    inverseSurface = Paper, inverseOnSurface = Ink, inversePrimary = Ink,
)
private val TallyTypography = Typography().let { base -> base.copy(
    displayLarge = base.displayLarge.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    displayMedium = base.displayMedium.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    displaySmall = base.displaySmall.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    headlineLarge = base.headlineLarge.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    headlineMedium = base.headlineMedium.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    headlineSmall = base.headlineSmall.copy(fontFamily = UiFontFamily, fontWeight = FontWeight.Bold),
    titleLarge = base.titleLarge.copy(fontFamily = UiFontFamily),
    titleMedium = base.titleMedium.copy(fontFamily = UiFontFamily),
    titleSmall = base.titleSmall.copy(fontFamily = UiFontFamily),
    bodyLarge = base.bodyLarge.copy(fontFamily = UiFontFamily),
    bodyMedium = base.bodyMedium.copy(fontFamily = UiFontFamily),
    bodySmall = base.bodySmall.copy(fontFamily = UiFontFamily),
    labelLarge = base.labelLarge.copy(fontFamily = UiFontFamily),
    labelMedium = base.labelMedium.copy(fontFamily = UiFontFamily),
    labelSmall = base.labelSmall.copy(fontFamily = UiFontFamily),
    displayLargeEmphasized = base.displayLargeEmphasized.copy(fontFamily = UiFontFamily),
    displayMediumEmphasized = base.displayMediumEmphasized.copy(fontFamily = UiFontFamily),
    displaySmallEmphasized = base.displaySmallEmphasized.copy(fontFamily = UiFontFamily),
    headlineLargeEmphasized = base.headlineLargeEmphasized.copy(fontFamily = UiFontFamily),
    headlineMediumEmphasized = base.headlineMediumEmphasized.copy(fontFamily = UiFontFamily),
    headlineSmallEmphasized = base.headlineSmallEmphasized.copy(fontFamily = UiFontFamily),
    titleLargeEmphasized = base.titleLargeEmphasized.copy(fontFamily = UiFontFamily),
    titleMediumEmphasized = base.titleMediumEmphasized.copy(fontFamily = UiFontFamily),
    titleSmallEmphasized = base.titleSmallEmphasized.copy(fontFamily = UiFontFamily),
    bodyLargeEmphasized = base.bodyLargeEmphasized.copy(fontFamily = UiFontFamily),
    bodyMediumEmphasized = base.bodyMediumEmphasized.copy(fontFamily = UiFontFamily),
    bodySmallEmphasized = base.bodySmallEmphasized.copy(fontFamily = UiFontFamily),
    labelLargeEmphasized = base.labelLargeEmphasized.copy(fontFamily = UiFontFamily),
    labelMediumEmphasized = base.labelMediumEmphasized.copy(fontFamily = UiFontFamily),
    labelSmallEmphasized = base.labelSmallEmphasized.copy(fontFamily = UiFontFamily),
) }
private val TallyShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp), small = RoundedCornerShape(8.dp),
    medium = RoundedCornerShape(12.dp), large = RoundedCornerShape(16.dp), extraLarge = RoundedCornerShape(24.dp),
)

@Composable
fun TallyTheme(content: @Composable () -> Unit) {
    MaterialExpressiveTheme(motionScheme = MotionScheme.expressive(), colorScheme = if (isSystemInDarkTheme()) TallyDarkColors else TallyColors, typography = TallyTypography, shapes = TallyShapes, content = content)
}
