package com.universalsoul.companion;

import android.app.PendingIntent;
import android.appwidget.AppWidgetManager;
import android.appwidget.AppWidgetProvider;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.widget.RemoteViews;

import org.json.JSONObject;

/**
 * Home-screen companion face — mirrors PWA emotion eyes when the app updates presence.
 */
public class CompanionWidgetProvider extends AppWidgetProvider {
    public static final String PREFS = "CapacitorStorage";
    public static final String KEY = "usa_widget_presence";
    public static final String ACTION_REFRESH = "com.universalsoul.companion.ACTION_REFRESH_WIDGET";

    @Override
    public void onUpdate(Context context, AppWidgetManager appWidgetManager, int[] appWidgetIds) {
        for (int id : appWidgetIds) {
            updateOne(context, appWidgetManager, id, readPresence(context));
        }
    }

    @Override
    public void onReceive(Context context, Intent intent) {
        super.onReceive(context, intent);
        if (intent != null && ACTION_REFRESH.equals(intent.getAction())) {
            refreshAll(context);
        }
    }

    public static void refreshAll(Context context) {
        AppWidgetManager mgr = AppWidgetManager.getInstance(context);
        ComponentName name = new ComponentName(context, CompanionWidgetProvider.class);
        int[] ids = mgr.getAppWidgetIds(name);
        Presence p = readPresence(context);
        for (int id : ids) {
            updateOne(context, mgr, id, p);
        }
    }

    public static void writePresence(Context context, String json) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        prefs.edit().putString(KEY, json == null ? "" : json).apply();
        refreshAll(context);
    }

    private static Presence readPresence(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
        String raw = prefs.getString(KEY, "");
        Presence p = new Presence();
        if (raw == null || raw.isEmpty()) {
            return p;
        }
        try {
            JSONObject o = new JSONObject(raw);
            p.state = o.optString("state", "idle");
            p.emotion = o.optString("emotion", "idle");
            p.name = o.optString("name", "Soul");
        } catch (Exception ignored) {
            /* keep defaults */
        }
        return p;
    }

    private static void updateOne(Context context, AppWidgetManager mgr, int id, Presence p) {
        RemoteViews views = new RemoteViews(context.getPackageName(), R.layout.widget_companion);
        views.setTextViewText(R.id.widget_name, p.name != null && !p.name.isEmpty() ? p.name : "Soul");
        views.setTextViewText(R.id.widget_status, labelFor(p));

        int eyeColor = 0xFF0A1F18;
        int faceColor = 0xFF3ECF9A;
        String emo = p.emotion != null ? p.emotion : "idle";
        String st = p.state != null ? p.state : "idle";
        if ("thinking".equals(st) || "thinking".equals(emo)) {
            faceColor = 0xFF6A9EFF;
        } else if ("listening".equals(st) || "listening".equals(emo)) {
            faceColor = 0xFF2A9A72;
        } else if ("speaking".equals(st) || "happy".equals(emo) || "excited".equals(emo)) {
            faceColor = 0xFF3ECF9A;
        } else if ("concerned".equals(emo)) {
            faceColor = 0xFFD4A017;
        }
        views.setInt(R.id.widget_face, "setColorFilter", faceColor);
        views.setInt(R.id.widget_eye_left, "setColorFilter", eyeColor);
        views.setInt(R.id.widget_eye_right, "setColorFilter", eyeColor);

        Intent launch = new Intent(context, MainActivity.class);
        launch.setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent pi = PendingIntent.getActivity(
            context,
            0,
            launch,
            PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE
        );
        views.setOnClickPendingIntent(R.id.widget_root, pi);

        mgr.updateAppWidget(id, views);
    }

    private static String labelFor(Presence p) {
        String st = p.state != null ? p.state : "idle";
        if ("speaking".equals(st)) return "speaking";
        if ("listening".equals(st)) return "listening";
        if ("thinking".equals(st)) return "thinking";
        if ("excited".equals(p.emotion)) return "excited";
        if ("concerned".equals(p.emotion)) return "concerned";
        if ("happy".equals(p.emotion)) return "here with you";
        return "idle";
    }

    private static class Presence {
        String state = "idle";
        String emotion = "idle";
        String name = "Soul";
    }
}
