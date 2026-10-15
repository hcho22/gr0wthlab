// Synthetic stand-in for a Product's code, for gr0wthlab's claim checks.
enum SessionRules {
    /// Five minutes of a session counts as showing up for the day, however long it was planned to run.
    static let minutesToShowUp = 5

    static func showedUp(minutes: Int) -> Bool {
        minutes >= minutesToShowUp
    }

    /// A small space, such as a hallway, gets only moves done standing in place, with no equipment.
    static func moves(smallSpace: Bool) -> [Move] {
        smallSpace ? Move.all.filter { $0.inPlace && $0.equipment.isEmpty } : Move.all
    }
}
