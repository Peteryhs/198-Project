package com.jeevan.tally.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp

// Fixed brand colors: wallpaper-derived dynamic colors must never replace this palette.
private val TallyColors = lightColorScheme(
    primary = Ink, onPrimary = Paper, primaryContainer = Oat, onPrimaryContainer = Ink,
    secondary = Clay, onSecondary = White, secondaryContainer = Paper, onSecondaryContainer = Ink,
    tertiary = Clay, onTertiary = White, tertiaryContainer = Oat, onTertiaryContainer = Ink,
    background = Paper, onBackground = Ink,
    surface = Paper, onSurface = Ink, surfaceVariant = White, onSurfaceVariant = Ink,
    surfaceContainerLowest = White, surfaceContainerLow = White,
    surfaceContainer = Paper, surfaceContainerHigh = White, surfaceContainerHighest = Oat,
    surfaceBright = White, surfaceDim = Oat, surfaceTint = Ink,
    outline = Oat, outlineVariant = Oat,
    inverseSurface = Ink, inverseOnSurface = Paper, inversePrimary = Paper,
    error = Clay, onError = White, errorContainer = Paper, onErrorContainer = Clay,
    scrim = Ink,
    primaryFixed = Paper, primaryFixedDim = Oat, onPrimaryFixed = Ink, onPrimaryFixedVariant = Ink,
    secondaryFixed = Paper, secondaryFixedDim = Oat, onSecondaryFixed = Clay, onSecondaryFixedVariant = Ink,
    tertiaryFixed = Paper, tertiaryFixedDim = Oat, onTertiaryFixed = Clay, onTertiaryFixedVariant = Ink,
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
    medium = RoundedCornerShape(12.dp), large = RoundedCornerShape(16.dp), extraLarge = RoundedCornerShape(28.dp),
)

@Composable
fun TallyTheme(content: @Composable () -> Unit) {
    MaterialExpressiveTheme(motionScheme = MotionScheme.expressive(), colorScheme = TallyColors, typography = TallyTypography, shapes = TallyShapes, content = content)
}
