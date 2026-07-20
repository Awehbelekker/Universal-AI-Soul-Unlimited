package com.universalsoul.companion;

import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebView;

import com.getcapacitor.BridgeActivity;

/**
 * Capacitor host + JS bridge so the PWA can push emotion-eye state to the home widget.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        try {
            WebView webView = getBridge() != null ? getBridge().getWebView() : null;
            if (webView != null) {
                webView.addJavascriptInterface(new SoulWidgetBridge(), "SoulWidget");
            }
        } catch (Exception ignored) {
            /* bridge may not be ready yet on some devices */
        }
    }

    @Override
    public void onResume() {
        super.onResume();
        try {
            WebView webView = getBridge() != null ? getBridge().getWebView() : null;
            if (webView != null) {
                // Re-attach if the WebView was recreated
                webView.addJavascriptInterface(new SoulWidgetBridge(), "SoulWidget");
            }
            CompanionWidgetProvider.refreshAll(this);
        } catch (Exception ignored) {
            /* best-effort */
        }
    }

    private class SoulWidgetBridge {
        @JavascriptInterface
        public void update(String json) {
            CompanionWidgetProvider.writePresence(MainActivity.this.getApplicationContext(), json);
        }
    }
}
