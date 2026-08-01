#!/usr/bin/env python3
"""FMしおまちの日次放送原稿を生成する。

外部APIは使用しない。最初の7日間は町が成立する固定進行、
以降は町の記憶を参照したルールベース生成を行う。
"""

from __future__ import annotations

import json
import random
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
BROADCASTS_PATH = ROOT / "data" / "broadcasts.json"
STATE_PATH = ROOT / "canon" / "state.json"
START_DATE = date(2026, 8, 1)
JST = ZoneInfo("Asia/Tokyo")


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path: Path, value: dict) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
        file.write("\n")


def ensure_entity(collection: list[dict], name: str, entity_type: str, today: str) -> None:
    for entity in collection:
        if entity.get("name") == name:
            entity["mentions"] = int(entity.get("mentions", 1)) + 1
            if entity["mentions"] >= 2 and entity.get("status") == "unconfirmed":
                entity["status"] = "established"
            return
    collection.append(
        {
            "name": name,
            "type": entity_type,
            "first_seen": today,
            "mentions": 1,
            "status": "unconfirmed",
        }
    )


def fixed_first_week(day_number: int, today: str, state: dict) -> dict | None:
    entries: dict[int, dict] = {
        2: {
            "time": "07:18",
            "program": "朝のしおまち情報",
            "type": "交通情報",
            "title": "市役所前通りの車線規制",
            "text": (
                "午前7時18分、交通情報です。\n\n"
                "潮待市役所前の北通りでは、昨日の雨による路面点検のため、"
                "午前9時から片側一車線の通行規制が行われます。\n"
                "規制は正午までの予定です。付近を通行する方は、係員の案内に従ってください。\n\n"
                "以上、交通情報でした。"
            ),
            "entities": [("places", "潮待市役所", "public-office"), ("places", "北通り", "road")],
        },
        3: {
            "time": "12:06",
            "program": "お昼のしおまち便り",
            "type": "市政情報",
            "title": "住民票臨時交付窓口のお知らせ",
            "text": (
                "午後0時6分、潮待市からのお知らせです。\n\n"
                "市役所一階の臨時窓口では、本日から住民票の交付を受け付けます。\n"
                "潮待市にお住まいで、まだ住所が決まっていない方も申請できます。\n"
                "受付は午後4時30分までです。\n\n"
                "以上、潮待市からのお知らせでした。"
            ),
            "entities": [("organizations", "潮待市", "municipality")],
        },
        4: {
            "time": "17:42",
            "program": "夕方しおまち通信",
            "type": "催事情報",
            "title": "市制60周年記念行事",
            "text": (
                "午後5時42分、地域の催し物のお知らせです。\n\n"
                "潮待市では、市制60周年を記念した写真展を市民会館で開催しています。\n"
                "会場には、開市当時から現在までの町並みを記録した写真およそ120点が展示されています。\n"
                "入場は無料です。会期は8月9日までです。\n\n"
                "以上、地域の催し物のお知らせでした。"
            ),
            "entities": [("places", "潮待市民会館", "public-hall")],
        },
        5: {
            "time": "08:11",
            "program": "朝のしおまち情報",
            "type": "交通情報",
            "title": "旧潮待線代替バスの運行",
            "text": (
                "午前8時11分、交通情報です。\n\n"
                "旧潮待線の南駅から市役所前まで、代替バスが20分間隔で運行しています。\n"
                "線路跡付近では霧が出ているため、徒歩での通行は控えてください。\n"
                "最終便は午後8時40分です。\n\n"
                "以上、交通情報でした。"
            ),
            "entities": [("places", "旧潮待線", "railway"), ("places", "潮待南駅", "station")],
        },
        6: {
            "time": "22:31",
            "program": "海抜ゼロからこんばんは",
            "type": "お便り",
            "title": "ラジオネーム『岸壁の窓』さん",
            "text": (
                "ここで、番組に届いたお便りをご紹介します。\n\n"
                "『毎晩、仕事から帰る途中に聞いています。昨日は市役所前で雨宿りをしましたが、"
                "放送で聞いていたより建物が一階多く、少し驚きました。これからも地域の情報をお願いします』\n\n"
                "岸壁の窓さん、お便りありがとうございました。"
            ),
            "entities": [("people", "岸壁の窓", "listener")],
        },
        7: {
            "time": "06:55",
            "program": "朝のしおまち情報",
            "type": "局からのお知らせ",
            "title": "開局記念週間について",
            "text": (
                "FMしおまちからのお知らせです。\n\n"
                "当局は、潮待市からの放送要請を受けて開局し、本日で18年を迎えました。\n"
                "今週は開局記念週間として、過去の地域放送を一部再放送します。\n"
                "なお、開局以前の放送記録についても通常どおり受け付けています。\n\n"
                "これからもFMしおまちをよろしくお願いいたします。"
            ),
            "entities": [],
        },
    }

    entry = entries.get(day_number)
    if not entry:
        return None

    entity_refs = entry.pop("entities")
    for collection_name, name, entity_type in entity_refs:
        ensure_entity(state[collection_name], name, entity_type, today)
    return {"date": today, **entry}


def choose_place(state: dict, rng: random.Random) -> str:
    places = [item["name"] for item in state["places"] if item.get("status") != "retired"]
    return rng.choice(places or ["潮待市"])


def generated_entry(today: str, day_number: int, state: dict) -> dict:
    rng = random.Random(f"fm-shiomachi:{today}")
    place = choose_place(state, rng)
    ensure_entity(state["places"], place, "place", today)
    minute = rng.randrange(0, 60)

    normal_kind = rng.choice(["collection", "weather", "exhibition"])
    if normal_kind == "collection":
        entry = {
            "time": f"07:{minute:02d}",
            "program": "朝のしおまち情報",
            "type": "生活情報",
            "title": "資源回収日のお知らせ",
            "text": (
                f"午前7時{minute}分、地域のお知らせです。\n\n"
                f"{place}周辺では、本日、紙類とびん類の回収が行われます。"
                "指定の集積場所へ午前8時30分までにお出しください。\n\n"
                "以上、地域のお知らせでした。"
            ),
        }
    elif normal_kind == "weather":
        entry = {
            "time": f"17:{minute:02d}",
            "program": "夕方しおまち通信",
            "type": "気象情報",
            "title": "夕方から夜の天気",
            "text": (
                f"午後5時{minute}分、気象情報です。\n\n"
                f"{place}では、夜遅くにかけて雲が広がる見込みです。"
                "海沿いでは風が強まるため、戸締まりをご確認ください。\n\n"
                "以上、気象情報でした。"
            ),
        }
    else:
        entry = {
            "time": f"12:{minute:02d}",
            "program": "お昼のしおまち便り",
            "type": "催事情報",
            "title": "地域展示のお知らせ",
            "text": (
                f"午後0時{minute}分、催し物のお知らせです。\n\n"
                f"{place}では、地域の古い写真と生活用品を紹介する小規模展示が行われています。"
                "入場は無料です。\n\n"
                "以上、催し物のお知らせでした。"
            ),
        }

    # 異常は最大一件。毎日必ず発生させない。
    if day_number % 4 == 0:
        anomaly = rng.choice(["new-place", "time", "number", "subject"])
        if anomaly == "new-place":
            new_place = f"{place}{rng.choice(['地下分室', '海側出入口', '旧館', '夜間窓口'])}"
            ensure_entity(state["places"], new_place, "derived-place", today)
            entry = {
                "time": f"12:{minute:02d}",
                "program": "お昼のしおまち便り",
                "type": "施設情報",
                "title": f"{new_place}の利用案内",
                "text": (
                    f"午後0時{minute}分、施設利用のお知らせです。\n\n"
                    f"{new_place}は、本日午後1時から通常どおり利用できます。"
                    "入口が見つからない場合は、閉館後にもう一度お越しください。\n\n"
                    "以上、施設利用のお知らせでした。"
                ),
            }
        elif anomaly == "time":
            entry = {
                "time": f"07:{minute:02d}",
                "program": "朝のしおまち情報",
                "type": "催事情報",
                "title": "昨日開催予定の催しについて",
                "text": (
                    f"午前7時{minute}分、催し物のお知らせです。\n\n"
                    f"{place}で明日予定されていた催しは、昨日、予定どおり終了しました。"
                    "忘れ物の受け取りは開催前日まで受け付けています。\n\n"
                    "以上、催し物のお知らせでした。"
                ),
            }
        elif anomaly == "number":
            population = 42018 + day_number
            entry = {
                "time": f"17:{minute:02d}",
                "program": "夕方しおまち通信",
                "type": "市政情報",
                "title": "本日の人口速報",
                "text": (
                    f"午後5時{minute}分、人口速報です。\n\n"
                    f"本日午後5時現在の潮待市の人口は、前日より0.4人増えて{population}.4人です。"
                    "端数は夜間人口として集計されています。\n\n"
                    "以上、人口速報でした。"
                ),
            }
        else:
            entry = {
                "time": f"07:{minute:02d}",
                "program": "朝のしおまち情報",
                "type": "生活情報",
                "title": "帰宅支援窓口のお知らせ",
                "text": (
                    f"午前7時{minute}分、潮待市からのお知らせです。\n\n"
                    "市では、市内に住んだことのない住民を対象に帰宅支援を行っています。"
                    "本人確認には、まだ交付されていない住所が必要です。\n\n"
                    "以上、潮待市からのお知らせでした。"
                ),
            }

    return {"date": today, **entry}


def main() -> int:
    now = datetime.now(JST)
    today_date = now.date()
    today = today_date.isoformat()
    day_number = (today_date - START_DATE).days + 1

    if day_number < 1:
        print("連載開始日前のため生成しません。")
        return 0

    broadcasts = load_json(BROADCASTS_PATH)
    state = load_json(STATE_PATH)

    if any(item["date"] == today for item in broadcasts["broadcasts"]):
        print(f"{today} の放送は既に存在します。")
        return 0

    entry = fixed_first_week(day_number, today, state)
    if entry is None:
        entry = generated_entry(today, day_number, state)

    broadcasts["broadcasts"].append(entry)
    broadcasts["broadcasts"].sort(key=lambda item: item["date"])
    broadcasts["updated_at"] = now.isoformat(timespec="seconds")

    save_json(BROADCASTS_PATH, broadcasts)
    save_json(STATE_PATH, state)
    print(f"{today}: {entry['title']} を追加しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
