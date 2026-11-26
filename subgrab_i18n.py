# SubGrab - downloads and fixes subtitles for your videos
# Copyright (C) 2026 Megatro-nn
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""UI language strings shared by the Tk and Qt interfaces (English + Arabic, RTL flag)."""

# ---------------------------------------------------------------- languages
UI = {"lang": "en", "rtl": False}

AR = {
    "Auto Folder": "المجلد التلقائي", "Search": "بحث", "Subtitle Tools": "أدوات الترجمة", "Settings": "الإعدادات",
    "Movie / series folder:": "مجلد الفيلم / المسلسل:", "Browse...": "استعراض...", "Scan": "فحص",
    "Language:": "اللغة:", "Include subfolders": "تضمين المجلدات الفرعية", "Overwrite existing": "استبدال الموجود",
    "Subtitle options:": "خيارات الترجمة:", "Convert to UTF-8": "تحويل إلى UTF-8", "Convert to SRT": "تحويل إلى SRT",
    "Remove ads / watermarks": "إزالة الإعلانات", "Remove hearing-impaired tags": "إزالة وصف الأصوات (SDH)",
    "Add BOM (older TVs/players)": "إضافة BOM (للأجهزة القديمة)",
    "Watch this folder for new videos": "مراقبة المجلد للفيديوهات الجديدة",
    "Video file": "ملف الفيديو", "Detected as": "تم التعرف عليه", "Status": "الحالة",
    "Download subtitles": "تنزيل الترجمات", "Stop": "إيقاف", "Pick manually...": "اختيار يدوي...",
    "waiting": "في الانتظار", "searching...": "جارٍ البحث...", "has subtitle": "لديه ترجمة",
    "Drop folders or video files anywhere in this window": "اسحب المجلدات أو ملفات الفيديو وأفلتها في هذه النافذة",
    "Search Movie\\Series by Name or IMDB id": "ابحث عن فيلم أو مسلسل بالاسم أو رقم IMDB",
    "Results": "النتائج", "Source": "المصدر", "Subtitle / release": "الترجمة / الإصدار", "Language": "اللغة",
    "Uploader": "الرافع", "Download": "تنزيل", "Preview": "معاينة", "Open in browser": "فتح في المتصفح",
    "Use selected": "استخدام المحدد", "Close": "إغلاق", "Release": "الإصدار", "Score": "التقييم", "Match": "التطابق", "Why": "لماذا",
    "General": "عام", "Sources": "المصادر", "Subtitles": "الترجمات", "Archives": "الأرشيف", "Advanced": "متقدم",
    "About": "حول", "Save": "حفظ", "Test": "اختبار", "Saved.": "تم الحفظ.",
    "Interface language": "لغة الواجهة", "Theme": "المظهر", "Default language": "اللغة الافتراضية",
    "Download folder": "مجلد التنزيل", "Ask where to save every time": "اسأل عن مكان الحفظ كل مرة",
    "Extract .zip files after download": "فك ضغط ملفات zip بعد التنزيل",
    "Check for updates on start": "التحقق من التحديثات عند التشغيل",
    "Restart to apply language / theme changes.": "أعد تشغيل البرنامج لتطبيق اللغة / المظهر.",
    "Restart now": "إعادة التشغيل الآن",
    "Subtitle file:": "ملف الترجمة:", "Shift timing (ms):": "إزاحة التوقيت (مللي ثانية):",
    "Frame rate: from": "معدل الإطارات: من", "to": "إلى", "Replace the original (keeps a .bak copy)": "استبدال الأصل (مع نسخة .bak)",
    "Apply": "تطبيق", "Pick a subtitle file first.": "اختر ملف ترجمة أولاً.",
    "Use file hash when possible (exact sync)": "استخدام بصمة الملف عند الإمكان (مزامنة دقيقة)",
    "Save weak matches automatically": "حفظ التطابقات الضعيفة تلقائياً",
    "Also download a second language:": "تنزيل لغة ثانية أيضاً:", "None": "بدون",
    "Unpack RAR / 7z files with 7-Zip": "فك ضغط RAR / 7z باستخدام 7-Zip", "7-Zip path": "مسار 7-Zip",
    "Site addresses (change them if a site moves)": "عناوين المواقع (غيّرها إذا انتقل الموقع)",
    "Reset site addresses": "استعادة العناوين", "Open debug log": "فتح سجل الأخطاء", "Open data folder": "فتح مجلد البيانات",
    "Unofficial sources scrape websites: they can break when a site changes, may be blocked, and stay off until you enable them.":
        "المصادر غير الرسمية تقرأ صفحات المواقع: قد تتعطل عند تغيّر المواقع أو تُحظر، وتبقى معطّلة حتى تفعّلها.",
    "Check for updates": "التحقق من التحديثات", "Sources:": "المصادر:", "Credentials": "بيانات الدخول",
    "Rename video files to clean names:": "إعادة تسمية ملفات الفيديو بأسماء نظيفة:",
    "Preview renames": "معاينة إعادة التسمية", "Apply renames": "تنفيذ إعادة التسمية",
    "Undo last rename": "التراجع عن آخر إعادة تسمية", "Rename preview": "معاينة إعادة التسمية",
    "Pick a folder with videos first.": "اختر مجلداً يحتوي على فيديوهات أولاً.",
    "Nothing to rename - all names already look clean.": "لا شيء لإعادة تسميته - كل الأسماء نظيفة.",
    "Nothing to rename.": "لا شيء لإعادة تسميته.", "Renamed": "تمت إعادة التسمية:",
    "file(s). Use Undo to restore.": "ملف. يمكنك التراجع للاستعادة.", "Restored": "تمت الاستعادة:",
    "file(s).": "ملف.", "Nothing to undo.": "لا شيء للتراجع عنه.",
}


def T(s):
    return AR.get(s, s) if UI["lang"] == "ar" else s


