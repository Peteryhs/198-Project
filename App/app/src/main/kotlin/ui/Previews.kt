package com.tally.app.ui

import com.tally.app.contract.DeviceInfo
import com.tally.app.contract.FakeTallyBackend
import com.tally.app.contract.SessionState
import com.tally.app.contract.SetResult
import com.tally.app.contract.SetSummary
import com.tally.app.contract.Side
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

/** Preview data from an explicitly simulated set in FakeTallyBackend. */
class FakeFixture(val backend: FakeTallyBackend, val device: DeviceInfo, val result: SetResult, val summaries: List<SetSummary>)

fun fakeAfterOneSet(): FakeFixture = runBlocking {
    val fake = FakeTallyBackend()
    val device = fake.connect().getOrThrow()
    fake.startSet(Side.L).getOrThrow()
    val done = fake.session.first { it is SessionState.Done } as SessionState.Done
    FakeFixture(fake, device, done.result, fake.history().first())
}
