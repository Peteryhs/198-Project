package com.jeevan.tally.sensors

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow

data class SampleBatch(val samples: List<SensorSample>, val dropped: Long = 0)

/** Bounded FIFO; overload discards the oldest unread sample and reports every eviction. */
internal class SampleBuffer(private val capacity: Int) {
    init { require(capacity > 0) }
    private val data = arrayOfNulls<SensorSample>(capacity)
    private var head = 0
    private var size = 0
    private var dropped = 0L

    @Synchronized fun offer(sample: SensorSample) {
        if (size == capacity) {
            data[head] = null
            head = (head + 1) % capacity
            size--
            dropped++
        }
        data[(head + size) % capacity] = sample.copy(values = sample.values.copyOf())
        size++
    }

    @Synchronized fun drain(): SampleBatch {
        val result = ArrayList<SensorSample>(size)
        repeat(size) {
            result.add(checkNotNull(data[head]))
            data[head] = null
            head = (head + 1) % capacity
        }
        size = 0
        return SampleBatch(result, dropped).also { dropped = 0 }
    }
}

/** Independent bounded queues prevent a slow consumer from blocking the socket reader.
 * No replay: a new recording receives only samples published after subscription.
 * Cancellation unregisters the queue; the bus owns no threads or coroutine scopes.
 */
class BufferedSampleBus(private val capacity: Int = 4096, private val batchMillis: Long = 16) {
    init { require(capacity > 0); require(batchMillis > 0) }
    private class Subscriber(capacity: Int) {
        val buffer = SampleBuffer(capacity)
        val ready = Channel<Unit>(Channel.CONFLATED)
    }
    private val lock = Any()
    private val subscribers = mutableSetOf<Subscriber>()
    internal val subscriberCount get() = synchronized(lock) { subscribers.size }

    fun publish(sample: SensorSample) {
        synchronized(lock) {
            subscribers.forEach {
                it.buffer.offer(sample)
                it.ready.trySend(Unit)
            }
        }
    }

    fun batches(): Flow<SampleBatch> = flow {
        val subscriber = Subscriber(capacity)
        synchronized(lock) { subscribers.add(subscriber) }
        try {
            for (ignored in subscriber.ready) {
                delay(batchMillis)
                val batch = subscriber.buffer.drain()
                if (batch.samples.isNotEmpty()) emit(batch)
            }
        } finally {
            synchronized(lock) { subscribers.remove(subscriber) }
            subscriber.ready.close()
        }
    }
}
