package com.jeevan.tally.ui.theme

import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontStyle
import com.jeevan.tally.R
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp


// Same bundled family as res/font/atkinson_hyperlegible.xml, with explicit Compose weights.
val UiFontFamily = FontFamily(
    Font(R.font.atkinson_hyperlegible_regular, FontWeight.Normal),
    Font(R.font.atkinson_hyperlegible_bold, FontWeight.Bold),
    Font(R.font.atkinson_hyperlegible_italic, FontWeight.Normal, FontStyle.Italic),
    Font(R.font.atkinson_hyperlegible_bolditalic, FontWeight.Bold, FontStyle.Italic),
)

val ReadoutFontFamily = FontFamily.Monospace

val SectionLabel = TextStyle(
    fontFamily = UiFontFamily,
    fontWeight = FontWeight.Bold,
    fontSize = 13.sp,
)

val AppTitle = TextStyle(
    fontFamily = UiFontFamily,
    fontWeight = FontWeight.Bold,
    fontSize = 20.sp,
)

val ReadoutLarge = TextStyle(
    fontFamily = ReadoutFontFamily,
    fontFeatureSettings = "tnum",
    fontWeight = FontWeight.Medium,
    fontSize = 26.sp,
)

val ReadoutMedium = TextStyle(
    fontFamily = ReadoutFontFamily,
    fontFeatureSettings = "tnum",
    fontWeight = FontWeight.Medium,
    fontSize = 16.sp,
)

val ReadoutSmall = TextStyle(
    fontFamily = ReadoutFontFamily,
    fontFeatureSettings = "tnum",
    fontWeight = FontWeight.Normal,
    fontSize = 12.sp,
)
