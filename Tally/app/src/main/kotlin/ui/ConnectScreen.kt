package com.tally.app.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.ColorFilter
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.tally.app.R
import com.tally.app.contract.LinkState

@Composable
fun ConnectScreen(
    link: LinkState,
    message: String?,
    onConnect: () -> Unit,
    onContinue: () -> Unit,
    continueLabel: String = "Continue",
    passphrase: String = "",
    onPassphraseChange: (String) -> Unit = {},
    connectEnabled: Boolean = true,
    connectionFailed: Boolean = false,
) {
    val failed = link is LinkState.Lost || (link == LinkState.Disconnected && connectionFailed)
    TallyScreenFrame("Connect", actions = {
        when (link) {
            is LinkState.Connected -> PrimaryAction(continueLabel, onClick = onContinue)
            LinkState.Joining, LinkState.Connecting -> PrimaryAction("Connecting", enabled = false) {}
            LinkState.Disconnected, is LinkState.Lost -> PrimaryAction(
                if (failed) "Try again" else "Connect", enabled = connectEnabled, onClick = onConnect,
            )
        }
    }) { viewport ->
        Column(
            viewport.verticalScroll(rememberScrollState()).padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(20.dp, Alignment.CenterVertically),
        ) {
            when {
                failed -> Image(
                    painter = painterResource(R.drawable.ic_wifi_off),
                    contentDescription = "No Wi-Fi connection to Tally",
                    modifier = Modifier.size(144.dp),
                    alpha = 0.25f,
                    colorFilter = ColorFilter.tint(MaterialTheme.colorScheme.onSurface),
                )
                link is LinkState.Connected -> Text("Connected to Tally", style = MaterialTheme.typography.headlineMedium)
                link == LinkState.Disconnected -> Text("Connect to Tally", style = MaterialTheme.typography.headlineMedium)
                else -> LinearProgressIndicator(Modifier.fillMaxWidth())
            }
            if (link == LinkState.Disconnected || link is LinkState.Lost) {
                OutlinedTextField(
                    modifier = Modifier.fillMaxWidth(),
                    value = passphrase,
                    onValueChange = onPassphraseChange,
                    label = { Text("Wi-Fi password") },
                    supportingText = { Text("Leave blank for an open network.") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
                )
            }
            val guidance = message ?: when {
                failed -> "Check Wi-Fi, Tally’s power, and the password."
                link == LinkState.Joining -> "Approve the Tally Wi-Fi request."
                else -> null
            }
            if (guidance != null) Text(guidance, style = MaterialTheme.typography.bodyMedium, textAlign = TextAlign.Center)
        }
    }
}

@Preview(showBackground = true, heightDp = 800)
@Composable
private fun ConnectedPreview() {
    val f = fakeAfterOneSet()
    TallyTheme { ConnectScreen(f.backend.link.value, null, {}, {}) }
}

@Preview(showBackground = true, heightDp = 800)
@Composable
private fun DisconnectedPreview() {
    TallyTheme { ConnectScreen(LinkState.Disconnected, null, {}, {}) }
}

@Preview(showBackground = true, heightDp = 800)
@Composable
private fun FailedPreview() {
    TallyTheme { ConnectScreen(LinkState.Disconnected, null, {}, {}, connectionFailed = true) }
}
