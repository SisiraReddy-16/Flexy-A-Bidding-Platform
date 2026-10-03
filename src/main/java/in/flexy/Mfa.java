package in.flexy;

import com.google.zxing.BarcodeFormat;
import com.google.zxing.client.j2se.MatrixToImageWriter;
import com.google.zxing.qrcode.QRCodeWriter;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.io.ByteArrayOutputStream;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.util.Base64;

/** TOTP (Google-Authenticator compatible) – port of mfa_service.py (pyotp/qrcode). */
public final class Mfa {
    private Mfa() {}
    private static final String B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

    public static String generateSecret() {
        byte[] b = new byte[20]; new SecureRandom().nextBytes(b);
        StringBuilder sb = new StringBuilder(); int buf = 0, bits = 0;
        for (byte x : b) { buf = (buf << 8) | (x & 0xff); bits += 8; while (bits >= 5) { sb.append(B32.charAt((buf >> (bits - 5)) & 31)); bits -= 5; } }
        return sb.toString();
    }
    private static byte[] decode(String s) {
        ByteArrayOutputStream o = new ByteArrayOutputStream(); int buf = 0, bits = 0;
        for (char c : s.toUpperCase().replace("=", "").toCharArray()) {
            int v = B32.indexOf(c); if (v < 0) continue;
            buf = (buf << 5) | v; bits += 5;
            if (bits >= 8) { o.write((buf >> (bits - 8)) & 0xff); bits -= 8; }
        }
        return o.toByteArray();
    }
    public static String uri(String secret, String username) {
        String u = URLEncoder.encode(username, StandardCharsets.UTF_8).replace("+", "%20");
        return "otpauth://totp/Flexy:" + u + "?secret=" + secret + "&issuer=Flexy";
    }
    public static String qrBase64(String text) {
        try {
            var matrix = new QRCodeWriter().encode(text, BarcodeFormat.QR_CODE, 300, 300);
            var out = new ByteArrayOutputStream();
            MatrixToImageWriter.writeToStream(matrix, "PNG", out);
            return Base64.getEncoder().encodeToString(out.toByteArray());
        } catch (Exception e) { throw new RuntimeException(e); }
    }
    private static String code(byte[] key, long counter) throws Exception {
        byte[] msg = new byte[8];
        for (int i = 7; i >= 0; i--) { msg[i] = (byte) (counter & 0xff); counter >>= 8; }
        Mac mac = Mac.getInstance("HmacSHA1"); mac.init(new SecretKeySpec(key, "HmacSHA1"));
        byte[] h = mac.doFinal(msg); int off = h[h.length - 1] & 0xf;
        int bin = ((h[off] & 0x7f) << 24) | ((h[off + 1] & 0xff) << 16) | ((h[off + 2] & 0xff) << 8) | (h[off + 3] & 0xff);
        return String.format("%06d", bin % 1_000_000);
    }
    public static boolean verify(String secret, String c) {
        try {
            byte[] key = decode(secret); long ctr = System.currentTimeMillis() / 1000 / 30;
            for (int w = -1; w <= 1; w++) if (code(key, ctr + w).equals(c.trim())) return true;
        } catch (Exception ignored) {}
        return false;
    }
}
