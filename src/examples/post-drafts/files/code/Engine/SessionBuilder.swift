// Synthetic stand-in for a Product's code, for gr0wthlab's claim checks.
enum SessionBuilder {
    /// Builds a session on the device with no network access.
    static func buildOffline(minutes: Int) -> Session {
        Session.assemble(minutes: minutes, source: .onDevice)
    }
}
