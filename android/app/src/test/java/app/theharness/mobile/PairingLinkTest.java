package app.theharness.mobile;

import org.junit.Test;
import static org.junit.Assert.*;

public class PairingLinkTest {
    private static final String LINK = "theharness://pair?v=1&endpoint=https%3A%2F%2Fcomputer.example.ts.net&pairing_id=abc_123&secret=secret-123";
    @Test public void validPairing() {
        PairingLink pairing = PairingLink.parse(LINK);
        assertEquals("https://computer.example.ts.net", pairing.endpoint);
        assertEquals("abc_123", pairing.pairingId);
        assertEquals("secret-123", pairing.secret);
    }
    @Test public void rejectsUnsafeEndpoints() {
        for (String value : new String[]{"http://computer.example.ts.net", "https://evil.test", "https://example.ts.net.evil.test", "https://localhost", "https://user@computer.example.ts.net", "https://computer.example.ts.net/path", "https://computer.example.ts.net:444", "https://computer.example.ts.net?query=1", "javascript:alert(1)"}) {
            try { PairingLink.endpoint(value); fail(value); } catch (IllegalArgumentException expected) { }
        }
    }
    @Test public void rejectsMalformedOrAmbiguousPairings() {
        for (String value : new String[]{LINK + "&secret=other", LINK.replace("v=1", "v=2"), LINK.replace("secret=secret-123", "secret="), LINK.replace("theharness:", "https:"), LINK + "#fragment", LINK.replace("//pair?", "//user@pair?"), LINK.replace("&pairing_id=abc_123", "")}) {
            try { PairingLink.parse(value); fail(value); } catch (IllegalArgumentException expected) { }
        }
    }
}
