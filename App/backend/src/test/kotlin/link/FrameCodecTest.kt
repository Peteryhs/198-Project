package com.tally.app.backend.link

import org.junit.Test

class FrameCodecTest {
    @Test fun roundTripAndRejectMalformedFrames() = FrameCodecChecks.run()
}
