package com.tally.app.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.tally.app.contract.SetId
import com.tally.app.contract.SetSummary

@Composable
fun HomeScreen(
    sets: List<SetSummary>,
    setInProgress: Boolean,
    onStart: () -> Unit,
    onOpen: (SetId) -> Unit,
    onSettings: () -> Unit,
) = TallyScreenFrame("Home", actions = {
    PrimaryAction(if (setInProgress) "Return to the current set" else "Start a new set", onClick = onStart)
    SecondaryAction("Settings", onClick = onSettings)
}) { modifier ->
    val orderedSets = remember(sets) { sets.sortedByDescending { it.startedAtEpochMs } }
    LazyColumn(modifier.fillMaxWidth(), contentPadding = PaddingValues(24.dp)) {
        item {
            Column(
                Modifier.padding(bottom = 24.dp),
                verticalArrangement = Arrangement.spacedBy(24.dp),
            ) {
                Text("Tally", style = MaterialTheme.typography.displayLarge)
                SectionLabel("Recent sets")
                if (sets.isEmpty()) Body("No sets yet. Each set you record appears here.")
            }
        }
        items(orderedSets, key = { it.id.raw.toLong() }) { set ->
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            Column(
                Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(set.id) }.padding(vertical = 16.dp)
            ) {
                // The verdict, rep count and class all come from the scorer, so each is labelled as an estimate.
                val verdict = verdictWords(set.status, set.wrong,
                    set.status == "scored" && set.intendedExercise != null && set.exercise != set.intendedExercise)
                Text(if (set.wrong != null) "$verdict, estimated" else verdict, style = MaterialTheme.typography.titleLarge)
                val reps = if (set.repCount == 1) "1 rep, estimated" else "${set.repCount} reps, estimated"
                Text(listOfNotNull(sideWords(set.side), reps, set.exercise?.let { "${exerciseWords(it)}, estimated" }).joinToString(" · "),
                    style = MaterialTheme.typography.bodyMedium)
                Text(dateWords(set.startedAtEpochMs), style = MaterialTheme.typography.bodySmall)
            }
        }
        if (sets.isNotEmpty()) item {
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

@Preview(showBackground = true, heightDp = 900)
@Composable
private fun HomePreview() {
    val fake = fakeAfterOneSet()
    TallyTheme { HomeScreen(fake.summaries, false, {}, {}, {}) }
}

@Preview(showBackground = true)
@Composable
private fun HomeEmptyPreview() = TallyTheme { HomeScreen(emptyList(), false, {}, {}, {}) }
