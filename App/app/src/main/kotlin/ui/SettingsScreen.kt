package com.tally.app.ui

import android.content.res.Configuration
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp

@Composable
fun SettingsScreen(
    darkMode: Boolean,
    onDarkModeChange: (Boolean) -> Unit,
    geminiKey: String,
    onGeminiKeyChange: (String) -> Unit,
    geminiStatus: String?,
    onCalibrate: () -> Unit,
    onDiagnostics: () -> Unit,
    onClose: () -> Unit,
) = TallyScreen("Settings", actions = {
    SecondaryAction("Back", onClick = onClose)
}) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionLabel("Appearance")
        SecondaryAction(if (darkMode) "Dark mode · On" else "Dark mode · Off") {
            onDarkModeChange(!darkMode)
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionLabel("Device and support")
        SecondaryAction("Calibrate sensors", onClick = onCalibrate)
        SecondaryAction("Diagnostics", onClick = onDiagnostics)
    }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionLabel("Gemini scoring")
        Body("An API key lets Tally send sensor data to Google Gemini for scoring. If Gemini is unavailable, Tally scores on this phone.")
        OutlinedTextField(
            value = geminiKey,
            onValueChange = onGeminiKeyChange,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Gemini API key") },
            supportingText = {
                Text(if (geminiKey.isBlank()) "Get a key from Google AI Studio." else "Key saved on this phone.")
            },
            singleLine = true,
            visualTransformation = PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
        )
        if (geminiStatus != null) Text(geminiStatus, style = MaterialTheme.typography.bodyMedium)
    }
}

@Preview(name = "Light", showBackground = true, heightDp = 800)
@Preview(name = "Dark", showBackground = true, heightDp = 800, uiMode = Configuration.UI_MODE_NIGHT_YES)
@Composable
private fun SettingsPreview() {
    val darkMode = isSystemInDarkTheme()
    TallyTheme(darkMode) {
        SettingsScreen(darkMode, {}, "", {}, null, {}, {}, {})
    }
}
