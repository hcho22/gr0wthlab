// Synthetic stand-in for a Product's code, for gr0wthlab's claim checks.
import SwiftUI

struct ReadyScreen: View {
    let session: Session

    var body: some View {
        // The session is built before the first frame, so the app opens onto it.
        SessionList(session: session)
        StartButton(action: start)
    }
}
