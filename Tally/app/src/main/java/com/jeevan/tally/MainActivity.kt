package com.jeevan.tally

import android.os.Bundle
import androidx.compose.runtime.*
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.foundation.layout.Column
import com.jeevan.tally.recording.RecordingStore
import java.io.File
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import androidx.lifecycle.ViewModelProvider
import com.jeevan.tally.recording.ExperimentSession
import com.jeevan.tally.recording.ExerciseSetSession
import com.jeevan.tally.ui.ExerciseScreen
import com.jeevan.tally.ui.SetDetailScreen
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.jeevan.tally.ui.ExperimentScreen
import com.jeevan.tally.ui.HomeScreen
import com.jeevan.tally.ui.theme.TallyTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        setContent {
            TallyTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    val navController = rememberNavController()
                    NavHost(navController = navController, startDestination = "home") {
                        composable("home") {
                            HomeScreen(context = this@MainActivity, onSelect = { id ->
                                navController.navigate("experiment/$id")
                            }, onOpenRecording = { id, recording ->
                                navController.navigate("experiment/$id?recording=$recording")
                            }, onStartSet = {
                                navController.navigate("set")
                            }, onOpenSet = { id ->
                                navController.navigate("set/$id")
                            })
                        }
                        composable("set") { backStackEntry ->
                            ExerciseScreen(session = ViewModelProvider(backStackEntry)[ExerciseSetSession::class.java]) {
                                navController.popBackStack()
                            }
                        }
                        composable("set/{id}", arguments = listOf(navArgument("id") { type = NavType.StringType })) { backStackEntry ->
                            val id = backStackEntry.arguments?.getString("id") ?: return@composable
                            SetDetailScreen(id) { navController.popBackStack() }
                        }
                        composable(
                            route = "experiment/{id}?recording={recording}",
                            arguments = listOf(navArgument("id") { type = NavType.StringType },
                                navArgument("recording") { type = NavType.StringType; nullable = true; defaultValue = null }),
                        ) { backStackEntry ->
                            val id = backStackEntry.arguments?.getString("id") ?: return@composable
                            val recordingId = backStackEntry.arguments?.getString("recording")
                            var loadError by remember(id, recordingId) { mutableStateOf(false) }
                            val entry by produceState<ExperimentEntry?>(null, id, recordingId) {
                                value = if (recordingId != null) {
                                    runCatching { withContext(Dispatchers.IO) {
                                        RecordingStore(File(filesDir, "recordings")).readInfo(recordingId).spec?.let(::ExperimentEntry)
                                    } }.getOrElse { loadError = true; null }
                                } else ExperimentRegistry.find(id)
                            }
                            if (entry == null) {
                                Column {
                                    Text(if (loadError) "Recording could not be opened." else "Loading sensor…")
                                    TextButton(onClick = { navController.popBackStack() }) { Text("Back") }
                                }
                                return@composable
                            }
                            ExperimentScreen(entry = entry!!, session = ViewModelProvider(backStackEntry)[ExperimentSession::class.java],
                                recordingId = backStackEntry.arguments?.getString("recording")) { navController.popBackStack() }
                        }
                    }
                }
            }
        }
    }
}
