// Synthetic stand-in for a Product's code, for gr0wthlab's claim checks.
struct ConsistencyScore {
    var value: Double

    mutating func recordMissedDay() {
        // A missed day lowers the score; nothing resets it to zero.
        value = max(floorValue, value - missPenalty)
    }
}
