package com.jeevan.tally.ui

import android.content.Context
import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Wifi
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusDirection
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.jeevan.tally.sensors.ArduinoLink
import com.jeevan.tally.ui.theme.ReadoutSmall

@Composable
fun ArduinoConnectionBar(context: Context, modifier: Modifier = Modifier) {
    val prefs = remember { context.getSharedPreferences("tally_prefs", Context.MODE_PRIVATE) }
    var host by rememberSaveable { mutableStateOf(prefs.getString("arduino_host", "192.168.240.1") ?: "") }
    var port by rememberSaveable { mutableStateOf(prefs.getString("arduino_port", "5555") ?: "") }
    val status by ArduinoLink.status.collectAsState()
    val error by ArduinoLink.errorMessage.collectAsState()
    val focus = LocalFocusManager.current
    val scheme = MaterialTheme.colorScheme
    val connected = status == ArduinoLink.Status.CONNECTED
    val connecting = status == ArduinoLink.Status.CONNECTING
    val validPort = port.toIntOrNull()?.let { it in 1..65535 } == true
    val canConnect = host.isNotBlank() && validPort && !connecting && !connected
    val connect = {
        if (canConnect) {
            focus.clearFocus()
            prefs.edit().putString("arduino_host", host.trim()).putString("arduino_port", port).apply()
            ArduinoLink.connect(host.trim(), port.toInt())
        }
    }
    val label = when (status) {
        ArduinoLink.Status.CONNECTED -> "Connected"
        ArduinoLink.Status.CONNECTING -> "Connecting…"
        ArduinoLink.Status.ERROR -> "Connection failed"
        else -> "Disconnected"
    }
    Card(modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large,
        colors = CardDefaults.cardColors(containerColor = scheme.surfaceContainerLow)) {
        Column(Modifier.animateContentSize(animationSpec = MaterialTheme.motionScheme.defaultSpatialSpec())
            .padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(if (connected) Icons.Filled.CheckCircle else Icons.Filled.Wifi, null,
                    tint = scheme.primary, modifier = Modifier.size(24.dp))
                Column(Modifier.weight(1f)) {
                    Text("Arduino", style = MaterialTheme.typography.titleMediumEmphasized)
                    Text(label, style = MaterialTheme.typography.bodySmall,
                        color = if (status == ArduinoLink.Status.ERROR) scheme.error else scheme.onSurfaceVariant,
                        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                }
            }
            if (connecting) LinearProgressIndicator(Modifier.fillMaxWidth())
            if (!connected) {
                BoxWithConstraints {
                    val stacked = maxWidth < 300.dp || LocalDensity.current.fontScale > 1.3f
                    val hostField: @Composable (Modifier) -> Unit = { fieldModifier ->
                        OutlinedTextField(host, { host = it.trim() }, label = { Text("Board address") },
                            singleLine = true, enabled = !connecting, modifier = fieldModifier,
                            shape = MaterialTheme.shapes.medium,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri, imeAction = ImeAction.Next),
                            keyboardActions = KeyboardActions(onNext = { focus.moveFocus(FocusDirection.Next) }))
                    }
                    val portField: @Composable (Modifier) -> Unit = { fieldModifier ->
                        OutlinedTextField(port, { port = it.filter(Char::isDigit).take(5) }, label = { Text("Port") },
                            singleLine = true, enabled = !connecting, isError = port.isNotEmpty() && !validPort,
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number, imeAction = ImeAction.Done),
                            keyboardActions = KeyboardActions(onDone = { connect() }),
                            modifier = fieldModifier, shape = MaterialTheme.shapes.medium)
                    }
                    if (stacked) Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        hostField(Modifier.fillMaxWidth()); portField(Modifier.fillMaxWidth())
                    } else Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        hostField(Modifier.weight(2f)); portField(Modifier.weight(1f))
                    }
                }
                if (port.isNotEmpty() && !validPort) Text("Use a port from 1 to 65535.",
                    color = scheme.error, style = MaterialTheme.typography.bodySmall)
                if (status == ArduinoLink.Status.ERROR) Text(error ?: "Check the address and Wi-Fi connection.",
                    color = scheme.error, style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite })
                else if (!connecting) Text("Use the same Wi-Fi network as your board.",
                    color = scheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
            } else Text("${host.trim()}:$port", style = ReadoutSmall, color = scheme.onSurfaceVariant)
            if (connected || connecting) OutlinedButton(onClick = { ArduinoLink.disconnect() },
                shapes = ButtonDefaults.shapes(), modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) {
                Text(if (connecting) "Cancel connection" else "Disconnect")
            } else Button(onClick = connect, enabled = canConnect, shapes = ButtonDefaults.shapes(),
                modifier = Modifier.fillMaxWidth().heightIn(min = 56.dp)) { Text("Connect to board") }
        }
    }
}
