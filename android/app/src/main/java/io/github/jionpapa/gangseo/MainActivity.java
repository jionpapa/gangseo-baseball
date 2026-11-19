package io.github.jionpapa.gangseo;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.net.ConnectivityManager;
import android.net.NetworkCapabilities;
import android.net.Uri;
import android.os.Bundle;
import android.view.Window;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

/**
 * 강서리그 — 앱 화면(WebView)으로 GitHub Pages의 앱을 띄웁니다.
 * 화면과 기록 데이터는 인터넷에서 받아오므로 데이터가 갱신되면 앱을 다시 깔지 않아도 반영됩니다.
 * 인터넷이 없으면 마지막으로 받아 둔 화면·기록을 보여줍니다.
 */
public class MainActivity extends Activity {

    private static final String HOME = "https://jionpapa.github.io/gangseo-baseball/";
    private static final String HOST = "jionpapa.github.io";

    private WebView web;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        Window w = getWindow();
        w.setStatusBarColor(Color.parseColor("#14213D"));
        w.setNavigationBarColor(Color.WHITE);

        web = new WebView(this);
        web.setBackgroundColor(Color.parseColor("#F3F4F7"));
        setContentView(web);

        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setCacheMode(isOnline() ? WebSettings.LOAD_DEFAULT : WebSettings.LOAD_CACHE_ELSE_NETWORK);

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (HOST.equals(uri.getHost())) return false;
                try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); } catch (Exception ignored) { }
                return true;
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) showOffline();
            }
        });

        if (savedInstanceState != null) web.restoreState(savedInstanceState);
        else web.loadUrl(HOME);
    }

    private boolean isOnline() {
        try {
            ConnectivityManager cm = (ConnectivityManager) getSystemService(CONNECTIVITY_SERVICE);
            NetworkCapabilities nc = cm.getNetworkCapabilities(cm.getActiveNetwork());
            return nc != null && nc.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET);
        } catch (Exception e) {
            return true;
        }
    }

    private void showOffline() {
        String html = "<!doctype html><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                + "<body style='font-family:sans-serif;text-align:center;padding:30vh 24px 0;color:#333'>"
                + "<h3>인터넷에 연결되지 않았습니다</h3><p style='color:#777'>처음 한 번은 인터넷이 필요합니다.<br>연결을 확인한 뒤 다시 시도해 주세요.</p>"
                + "<button style='margin-top:16px;padding:12px 28px;border:0;border-radius:10px;background:#14213d;color:#fff;font-size:16px' "
                + "onclick=\"location.href='" + HOME + "'\">다시 시도</button></body>";
        web.loadDataWithBaseURL(null, html, "text/html", "utf-8", null);
    }

    @Override
    public void onBackPressed() {
        // 앱 안에서 이전 화면이 있으면 그리로, 없으면 앱을 닫습니다
        web.evaluateJavascript("(window.__appBack&&window.__appBack())===true", value -> {
            if ("true".equals(value)) return;
            if (web.canGoBack()) web.goBack();
            else finish();
        });
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        super.onSaveInstanceState(outState);
        web.saveState(outState);
    }

    @Override
    protected void onPause() { web.onPause(); super.onPause(); }

    @Override
    protected void onResume() { super.onResume(); web.onResume(); }

    @Override
    protected void onDestroy() { web.destroy(); super.onDestroy(); }
}
