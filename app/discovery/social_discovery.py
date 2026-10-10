import re
import urllib.parse
from typing import List, Dict, Any, Optional


class SocialDiscoveryService:
    """
    Service for discovering, resolving, and enriching social media networks
    (X/Twitter, YouTube, Telegram, Substack/Web) and background profiles for
    analyst candidates and speakers.
    """

    # Alias mapping (Russian / alternative spellings -> canonical key)
    NAME_ALIASES: Dict[str, str] = {
        "артур хейс": "arthur hayes",
        "майкл сэйлор": "michael saylor",
        "майкл сейлор": "michael saylor",
        "виталик бутерин": "vitalik buterin",
        "кэти вуд": "cathie wood",
        "питер шифф": "peter schiff",
        "рауль пал": "raoul pal",
        "питер брандт": "peter brandt",
        "том ли": "tom lee",
        "бенджамин коуэн": "benjamin cowen",
        "вилли ву": "willy woo",
        "лин олден": "lyn alden",
        "дэн тапиеро": "dan tapiero",
        "илон маск": "elon musk",
        "роберт кийосаки": "robert kiyosaki",
        "robert kiyosaki": "robert kiyosaki",
        "александр герчик": "александр герчик",
        "евгений коган": "евгений коган",
        "василий олейник": "василий олейник",
        "рафаэль манвелян": "рафаэль манвелян",
        "анатолий радченко": "анатолий радченко",
        "кирилл эванс": "кирилл эванс",
        "михаил хазин": "михаил хазин",
        "сэм альтман": "sam altman",
        "sam altman": "sam altman",
    }

    CURATED_ANALYSTS: List[Dict[str, Any]] = [
        {
            "name": "Arthur Hayes",
            "domain": "crypto",
            "channel": "Maelstrom & Substack",
            "bio": "Сооснователь BitMEX, глава фонда Maelstrom, макро- и крипто-эссеист",
            "quote": "Глобальное расширение долларовой ликвидности ФРС и Казначейством США приведет к параболическому росту Bitcoin до $150,000–$200,000.",
            "socials": [
                {"platform": "x", "identifier": "@CryptoHayes", "url": "https://x.com/CryptoHayes", "title": "X: @CryptoHayes"},
                {"platform": "web", "identifier": "Substack", "url": "https://cryptohayes.substack.com", "title": "Substack: Arthur Hayes"},
                {"platform": "youtube", "identifier": "Maelstrom", "url": "https://www.youtube.com/results?search_query=Arthur+Hayes+interview", "title": "YouTube: Интервью"}
            ],
            "predictions": [
                {"event_hypothesis": "Bitcoin превысит $150,000 на фоне притока глобальной ликвидности", "speaker_confidence": 0.85, "domain": "crypto"}
            ]
        },
        {
            "name": "Michael Saylor",
            "domain": "crypto",
            "channel": "MicroStrategy",
            "bio": "Исполнительный председатель Strategy (MicroStrategy), институциональный биткоин-максималист",
            "quote": "Институциональное принятие и дефицит предложения после халвинга делают Биткоин главным резервным активом десятилетия.",
            "socials": [
                {"platform": "x", "identifier": "@saylor", "url": "https://x.com/saylor", "title": "X: @saylor"},
                {"platform": "youtube", "identifier": "MicroStrategy", "url": "https://www.youtube.com/@MicroStrategy", "title": "YouTube: Strategy"},
                {"platform": "web", "identifier": "Hope.com", "url": "https://www.hope.com", "title": "Web: Hope.com"}
            ],
            "predictions": [
                {"event_hypothesis": "Институциональный спрос через ETF поднимет Bitcoin выше $150,000", "speaker_confidence": 0.92, "domain": "crypto"}
            ]
        },
        {
            "name": "Cathie Wood",
            "domain": "tech",
            "channel": "ARK Invest",
            "bio": "Основатель и CEO инвестиционного фонда ARK Invest, эксперт по инновациям и ИИ",
            "quote": "Конвергенция искусственного интеллекта, робототехники и блокчейна обеспечит взрывной рост капитализации технологического сектора.",
            "socials": [
                {"platform": "x", "identifier": "@CathieDWood", "url": "https://x.com/CathieDWood", "title": "X: @CathieDWood"},
                {"platform": "youtube", "identifier": "ARK Invest", "url": "https://www.youtube.com/@ARKInvest", "title": "YouTube: ARK Invest"},
                {"platform": "web", "identifier": "ark-invest.com", "url": "https://ark-invest.com", "title": "Web: ARK Invest"}
            ],
            "predictions": [
                {"event_hypothesis": "ИИ и автономные технологии увеличат капитализацию лидирующих тех-компаний более чем в 2 раза", "speaker_confidence": 0.88, "domain": "tech"}
            ]
        },
        {
            "name": "Vitalik Buterin",
            "domain": "crypto",
            "channel": "Ethereum Foundation",
            "bio": "Сооснователь Ethereum, исследователь криптографии и децентрализованных систем",
            "quote": "Масштабирование L2-сетей и снижение комиссий за счет обновлений протокола сделают Ethereum базовым слоем глобального интернета ценности.",
            "socials": [
                {"platform": "x", "identifier": "@VitalikButerin", "url": "https://x.com/VitalikButerin", "title": "X: @VitalikButerin"},
                {"platform": "youtube", "identifier": "Ethereum Foundation", "url": "https://www.youtube.com/@EthereumFoundation", "title": "YouTube: Ethereum"},
                {"platform": "web", "identifier": "vitalik.eth.limo", "url": "https://vitalik.eth.limo", "title": "Blog: vitalik.eth"}
            ],
            "predictions": [
                {"event_hypothesis": "Объем транзакций в L2-сетях Ethereum вырастет более чем в 5 раз", "speaker_confidence": 0.86, "domain": "crypto"}
            ]
        },
        {
            "name": "Raoul Pal",
            "domain": "macro",
            "channel": "Real Vision",
            "bio": "Бывший топ-менеджер Goldman Sachs, основатель Real Vision и Global Macro Investor",
            "quote": "Мы находимся в макроэкономической «Банановой зоне» — цикл глобального рефинансирования долгов подтолкнет криптоактивы и тех-сектор вверх.",
            "socials": [
                {"platform": "x", "identifier": "@RaoulGMI", "url": "https://x.com/RaoulGMI", "title": "X: @RaoulGMI"},
                {"platform": "youtube", "identifier": "Real Vision", "url": "https://www.youtube.com/@RealVisionFinance", "title": "YouTube: Real Vision"},
                {"platform": "web", "identifier": "realvision.com", "url": "https://www.realvision.com", "title": "Web: Real Vision"}
            ],
            "predictions": [
                {"event_hypothesis": "Solana и высокопроизводительные блокчейны покажут опережающую доходность в текущем макроцикле", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Peter Brandt",
            "domain": "crypto",
            "channel": "Factor Trading",
            "bio": "Легендарный биржевой трейдер с 40-летним стажем, автор классических трудов по графическому анализу",
            "quote": "Классические параболические паттерны указывают на продолжение долгосрочного бычьего канала по Bitcoin при удержании ключевых скользящих средних.",
            "socials": [
                {"platform": "x", "identifier": "@PeterLBrandt", "url": "https://x.com/PeterLBrandt", "title": "X: @PeterLBrandt"},
                {"platform": "youtube", "identifier": "Peter Brandt", "url": "https://www.youtube.com/results?search_query=Peter+Brandt+trading", "title": "YouTube: Factor Trading"},
                {"platform": "web", "identifier": "peterlbrandt.com", "url": "https://www.peterlbrandt.com", "title": "Web: Factor LLC"}
            ],
            "predictions": [
                {"event_hypothesis": "Bitcoin достигнет верхней границы логарифмического канала выше $125,000", "speaker_confidence": 0.78, "domain": "crypto"}
            ]
        },
        {
            "name": "Tom Lee",
            "domain": "macro",
            "channel": "Fundstrat Global Advisors",
            "bio": "Управляющий партнер и глава исследований Fundstrat, ведущий стратег Уолл-стрит",
            "quote": "Снижение инфляционного давления и разворот ФРС создадут мощный попутный ветер для индекса S&P 500 и цифровых активов.",
            "socials": [
                {"platform": "x", "identifier": "@fundstrat", "url": "https://x.com/fundstrat", "title": "X: @fundstrat"},
                {"platform": "youtube", "identifier": "Fundstrat", "url": "https://www.youtube.com/results?search_query=Tom+Lee+Fundstrat+CNBC", "title": "YouTube: CNBC / Fundstrat"},
                {"platform": "web", "identifier": "fundstrat.com", "url": "https://www.fundstrat.com", "title": "Web: Fundstrat"}
            ],
            "predictions": [
                {"event_hypothesis": "Индекс S&P 500 обновит исторический максимум на фоне смягчения политики ФРС", "speaker_confidence": 0.82, "domain": "macro"}
            ]
        },
        {
            "name": "Benjamin Cowen",
            "domain": "crypto",
            "channel": "Into The Cryptoverse",
            "bio": "Количественный аналитик, исследователь логарифмической регрессии и доминации Bitcoin",
            "quote": "Доминация Bitcoin традиционно растет на этапе ужесточения ликвидности перед началом широкого альтсезона.",
            "socials": [
                {"platform": "x", "identifier": "@intocryptoverse", "url": "https://x.com/intocryptoverse", "title": "X: @intocryptoverse"},
                {"platform": "youtube", "identifier": "Into The Cryptoverse", "url": "https://www.youtube.com/@intocryptoverse", "title": "YouTube: Benjamin Cowen"},
                {"platform": "telegram", "identifier": "@intocryptoverse", "url": "https://t.me/intocryptoverse", "title": "Telegram: Cryptoverse"}
            ],
            "predictions": [
                {"event_hypothesis": "Доминация Bitcoin удержится выше 55% до разворота монетарного цикла", "speaker_confidence": 0.80, "domain": "crypto"}
            ]
        },
        {
            "name": "Lyn Alden",
            "domain": "macro",
            "channel": "Lyn Alden Investment Strategy",
            "bio": "Макроэкономический исследователь, инженер и инвестиционный стратег",
            "quote": "Хронический фискальный дефицит США делает невозможным длительное удержание высоких реальных ставок без запуска печатного станка.",
            "socials": [
                {"platform": "x", "identifier": "@LynAldenContact", "url": "https://x.com/LynAldenContact", "title": "X: @LynAldenContact"},
                {"platform": "web", "identifier": "lynalden.com", "url": "https://www.lynalden.com", "title": "Web: LynAlden.com"},
                {"platform": "youtube", "identifier": "Lyn Alden", "url": "https://www.youtube.com/results?search_query=Lyn+Alden+macro", "title": "YouTube: Выступления"}
            ],
            "predictions": [
                {"event_hypothesis": "Рост госдолга США приведет к новой волне монетарного стимулирования и росту золота и BTC", "speaker_confidence": 0.85, "domain": "macro"}
            ]
        },
        {
            "name": "Willy Woo",
            "domain": "crypto",
            "channel": "On-Chain Mind",
            "bio": "Пионер ончейн-аналитики Bitcoin, создатель индикатора NVT Ratio",
            "quote": "Ончейн-потоки показывают рекордное накопление долгосрочными холдерами и уход монет с централизованных бирж.",
            "socials": [
                {"platform": "x", "identifier": "@woonomic", "url": "https://x.com/woonomic", "title": "X: @woonomic"},
                {"platform": "web", "identifier": "woobull.com", "url": "https://charts.woobull.com", "title": "Web: Woobull Charts"},
                {"platform": "youtube", "identifier": "Willy Woo", "url": "https://www.youtube.com/results?search_query=Willy+Woo+onchain", "title": "YouTube: On-chain обзоры"}
            ],
            "predictions": [
                {"event_hypothesis": "Сокращение биржевых резервов BTC вызовет шок предложения на спотовом рынке", "speaker_confidence": 0.81, "domain": "crypto"}
            ]
        },
        {
            "name": "Mert Mumtaz",
            "domain": "crypto",
            "channel": "Helius Labs",
            "bio": "CEO Helius Labs, ведущий инфраструктурный эксперт экосистемы Solana",
            "quote": "Параллельное исполнение и запуск клиентского обновления Firedancer выведут пропускную способность Solana на уровень традиционных бирж.",
            "socials": [
                {"platform": "x", "identifier": "@0xMert_", "url": "https://x.com/0xMert_", "title": "X: @0xMert_"},
                {"platform": "youtube", "identifier": "Helius Labs", "url": "https://www.youtube.com/@helius_labs", "title": "YouTube: Helius"},
                {"platform": "web", "identifier": "helius.dev", "url": "https://www.helius.dev", "title": "Web: Helius.dev"}
            ],
            "predictions": [
                {"event_hypothesis": "Solana обойдет Ethereum по суточному объему торгов на DEX", "speaker_confidence": 0.83, "domain": "crypto"}
            ]
        },
        {
            "name": "Dan Tapiero",
            "domain": "macro",
            "channel": "10T Holdings",
            "bio": "Основатель 10T Holdings и Gold Bullion International, макро-инвестор",
            "quote": "Институциональный капитал формирует долгосрочную аллокацию в экосистему цифровых активов и токенизированных реальных активов (RWA).",
            "socials": [
                {"platform": "x", "identifier": "@DTAPCAP", "url": "https://x.com/DTAPCAP", "title": "X: @DTAPCAP"},
                {"platform": "web", "identifier": "10tholdings.com", "url": "https://www.10tholdings.com", "title": "Web: 10T Holdings"},
                {"platform": "youtube", "identifier": "Dan Tapiero", "url": "https://www.youtube.com/results?search_query=Dan+Tapiero+macro", "title": "YouTube: Интервью"}
            ],
            "predictions": [
                {"event_hypothesis": "Капитализация рынка цифровых активов превысит $5 трлн в текущем цикле", "speaker_confidence": 0.79, "domain": "crypto"}
            ]
        },
        {
            "name": "Peter Schiff",
            "domain": "macro",
            "channel": "Euro Pacific Asset Management",
            "bio": "Главный экономист Euro Pacific Capital, сторонник золотого стандарта",
            "quote": "Инфляция в США далека от победы: реальная стоимость жизни продолжит расти, а золото обновит исторические максимумы.",
            "socials": [
                {"platform": "x", "identifier": "@PeterSchiff", "url": "https://x.com/PeterSchiff", "title": "X: @PeterSchiff"},
                {"platform": "youtube", "identifier": "Peter Schiff Show", "url": "https://www.youtube.com/@PeterSchiff", "title": "YouTube: Peter Schiff"},
                {"platform": "web", "identifier": "schiffradio.com", "url": "https://www.schiffradio.com", "title": "Web: SchiffRadio"}
            ],
            "predictions": [
                {"event_hypothesis": "Золото вырастет выше $3,000 за унцию на фоне ослабления доллара", "speaker_confidence": 0.87, "domain": "macro"}
            ]
        },
        {
            "name": "PlanB",
            "domain": "crypto",
            "channel": "Stock-to-Flow Model",
            "bio": "Институциональный квант-аналитик, автор модели дефицитности Bitcoin Stock-to-Flow (S2F)",
            "quote": "Математическая редкость Bitcoin после четвертого халвинга диктует движение средней цены цикла в диапазон выше $150,000.",
            "socials": [
                {"platform": "x", "identifier": "@100trillionUSD", "url": "https://x.com/100trillionUSD", "title": "X: @100trillionUSD"},
                {"platform": "youtube", "identifier": "PlanB", "url": "https://www.youtube.com/@100trillionUSD", "title": "YouTube: PlanB"},
                {"platform": "web", "identifier": "planbtc.com", "url": "https://planbtc.com", "title": "Web: PlanBTC"}
            ],
            "predictions": [
                {"event_hypothesis": "По модели Stock-to-Flow Bitcoin преодолеет отметку $150,000", "speaker_confidence": 0.88, "domain": "crypto"}
            ]
        },
        {
            "name": "Anthony Pompliano",
            "domain": "crypto",
            "channel": "Pomp Investments",
            "bio": "Основатель Professional Capital Management, ведущий The Pomp Podcast",
            "quote": "Уолл-стрит приняла Bitcoin в качестве цифрового золота, а розничный спрос только начинает возвращаться на рынок.",
            "socials": [
                {"platform": "x", "identifier": "@APompliano", "url": "https://x.com/APompliano", "title": "X: @APompliano"},
                {"platform": "youtube", "identifier": "Anthony Pompliano", "url": "https://www.youtube.com/@AnthonyPompliano", "title": "YouTube: Pomp Podcast"},
                {"platform": "web", "identifier": "pomp.substack.com", "url": "https://pomp.substack.com", "title": "Substack: The Pomp Letter"}
            ],
            "predictions": [
                {"event_hypothesis": "Приток капитала в спотовые Bitcoin ETF превысит $100 млрд", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Balaji Srinivasan",
            "domain": "tech",
            "channel": "The Network State",
            "bio": "Бывший CTO Coinbase и партнер a16z, технологический инвестор и футуролог",
            "quote": "ИИ-агенты и криптографическая верификация станут основой новой цифровой экономики в условиях кризиса доверия к традиционным институтам.",
            "socials": [
                {"platform": "x", "identifier": "@balajis", "url": "https://x.com/balajis", "title": "X: @balajis"},
                {"platform": "youtube", "identifier": "Network State", "url": "https://www.youtube.com/@thenetworkstate", "title": "YouTube: Network State"},
                {"platform": "web", "identifier": "thenetworkstate.com", "url": "https://thenetworkstate.com", "title": "Web: Network State"}
            ],
            "predictions": [
                {"event_hypothesis": "Автономные ИИ-агенты начнут массово использовать крипто-кошельки для микроплатежей", "speaker_confidence": 0.85, "domain": "tech"}
            ]
        },
        {
            "name": "Роберт Кийосаки",
            "domain": "macro",
            "channel": "Rich Dad Channel",
            "bio": "Инвестор, предприниматель, автор бестселлера «Богатый папа, бедный папа»",
            "quote": "Фиатный доллар теряет покупательную способность из-за печати денег — защищайте капитал в золоте, серебре и Биткоине.",
            "socials": [
                {"platform": "x", "identifier": "@theRealKiyosaki", "url": "https://x.com/theRealKiyosaki", "title": "X: @theRealKiyosaki"},
                {"platform": "youtube", "identifier": "The Rich Dad Channel", "url": "https://www.youtube.com/@TheRichDadChannel", "title": "YouTube: Rich Dad"},
                {"platform": "web", "identifier": "richdad.com", "url": "https://www.richdad.com", "title": "Web: RichDad.com"}
            ],
            "predictions": [
                {"event_hypothesis": "Золото и Биткоин покажут кратный рост на фоне девальвации фиатных валют", "speaker_confidence": 0.86, "domain": "macro"}
            ]
        },
        {
            "name": "Евгений Коган",
            "domain": "macro",
            "channel": "Bitkogan",
            "bio": "Инвестиционный банкир, профессор ВШЭ, автор проекта Bitkogan",
            "quote": "Цикл высоких ставок в мировой экономике подходит к пику — инвесторам стоит фиксировать высокую доходность и присматриваться к акциям роста.",
            "socials": [
                {"platform": "telegram", "identifier": "@bitkogan", "url": "https://t.me/bitkogan", "title": "Telegram: @bitkogan"},
                {"platform": "youtube", "identifier": "Bitkogan", "url": "https://www.youtube.com/@Bitkogan", "title": "YouTube: Bitkogan"},
                {"platform": "x", "identifier": "@bitkogan", "url": "https://x.com/search?q=Bitkogan", "title": "X: Bitkogan"}
            ],
            "predictions": [
                {"event_hypothesis": "Начало цикла снижения ключевых ставок поддержит рынок облигаций и золота", "speaker_confidence": 0.80, "domain": "macro"}
            ]
        },
        {
            "name": "Александр Герчик",
            "domain": "macro",
            "channel": "Gerchik & Co",
            "bio": "Профессиональный биржевой трейдер Уолл-стрит с 25-летним опытом без убыточных месяцев",
            "quote": "Торгуйте уровни и накопление крупного игрока: институциональные объемы показывают удержание ключевых зон поддержки по основным индексам.",
            "socials": [
                {"platform": "youtube", "identifier": "Александр Герчик", "url": "https://www.youtube.com/@AlexGerchik", "title": "YouTube: Александр Герчик"},
                {"platform": "telegram", "identifier": "@gerchik_official", "url": "https://t.me/s/gerchik_official", "title": "Telegram: Герчик"},
                {"platform": "x", "identifier": "@GerchikAlex", "url": "https://x.com/search?q=Alex+Gerchik", "title": "X: Alex Gerchik"}
            ],
            "predictions": [
                {"event_hypothesis": "Крупный институциональный капитал удержит восходящий тренд на фондовом рынке США", "speaker_confidence": 0.77, "domain": "macro"}
            ]
        },
        {
            "name": "Рафаэль Манвелян",
            "domain": "crypto",
            "channel": "Слезы Сатоши",
            "bio": "Криптоинвестор, автор одного из крупнейших русскоязычных аналитических каналов «Слезы Сатоши»",
            "quote": "Цикличность крипторынка сохраняется: основная фаза распределения альткоинов наступает после обновления исторического максимума по BTC.",
            "socials": [
                {"platform": "telegram", "identifier": "@slezisatoshi", "url": "https://t.me/s/slezisatoshi", "title": "Telegram: Слезы Сатоши"},
                {"platform": "youtube", "identifier": "Слезы Сатоши", "url": "https://www.youtube.com/@Slezisatoshi", "title": "YouTube: Слезы Сатоши"},
                {"platform": "x", "identifier": "@slezisatoshi", "url": "https://x.com/search?q=Слезы+Сатоши", "title": "X: Слезы Сатоши"}
            ],
            "predictions": [
                {"event_hypothesis": "Альтсезон начнется после снижения доминации Bitcoin ниже 54%", "speaker_confidence": 0.79, "domain": "crypto"}
            ]
        },
        {
            "name": "Василий Олейник",
            "domain": "macro",
            "channel": "Деньги не спят",
            "bio": "Инвестиционный эксперт, трейдер, соведущий канала «Деньги не спят»",
            "quote": "Перегретость технологического сектора требует осторожности: коррекция по мультипликаторам на рынке США станет проверкой для инвесторов.",
            "socials": [
                {"platform": "youtube", "identifier": "Деньги не спят", "url": "https://www.youtube.com/@dengi_ne_spyat", "title": "YouTube: Деньги не спят"},
                {"platform": "telegram", "identifier": "@dengi_ne_spyat", "url": "https://t.me/s/dengi_ne_spyat", "title": "Telegram: Деньги не спят"},
                {"platform": "x", "identifier": "@oleynik", "url": "https://x.com/search?q=Василий+Олейник", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "На фондовом рынке США произойдет техническая коррекция более чем на 10%", "speaker_confidence": 0.74, "domain": "macro"}
            ]
        },
        {
            "name": "Кирилл Эванс",
            "domain": "crypto",
            "channel": "Kirill Evans",
            "bio": "Криптовалютный аналитик, трейдер и основатель образовательного сообщества",
            "quote": "Институциональный ордерфлоу и притоки в спотовые ETF формируют прочную базу для дальнейшего роста стоимости Bitcoin и Ethereum.",
            "socials": [
                {"platform": "youtube", "identifier": "Kirill Evans", "url": "https://www.youtube.com/@KirillEvans", "title": "YouTube: Kirill Evans"},
                {"platform": "telegram", "identifier": "@kirillevans", "url": "https://t.me/s/kirillevans", "title": "Telegram: Kirill Evans"},
                {"platform": "x", "identifier": "@KirillEvans", "url": "https://x.com/search?q=Kirill+Evans+crypto", "title": "X: Kirill Evans"}
            ],
            "predictions": [
                {"event_hypothesis": "Ethereum обновит исторический максимум вслед за ростом Bitcoin", "speaker_confidence": 0.80, "domain": "crypto"}
            ]
        },
        {
            "name": "Анатолий Радченко",
            "domain": "crypto",
            "channel": "United Traders",
            "bio": "Управляющий партнер United Traders, алгоритмический трейдер и венчурный инвестор",
            "quote": "Сектор DeFi и пересечение ИИ с блокчейн-инфраструктурой станут главными драйверами венчурного капитала.",
            "socials": [
                {"platform": "youtube", "identifier": "United Traders", "url": "https://www.youtube.com/@UnitedTraders", "title": "YouTube: United Traders"},
                {"platform": "telegram", "identifier": "@radchenko_ut", "url": "https://t.me/s/radchenko_ut", "title": "Telegram: Радченко"},
                {"platform": "x", "identifier": "@utmagazine", "url": "https://x.com/search?q=United+Traders", "title": "X: United Traders"}
            ],
            "predictions": [
                {"event_hypothesis": "Токены AI-инфраструктуры и DeFi покажут опережающий рост капитализации", "speaker_confidence": 0.78, "domain": "crypto"}
            ]
        },
        {
            "name": "Sam Altman",
            "domain": "tech",
            "channel": "OpenAI",
            "bio": "CEO OpenAI, венчурный инвестор и бывший президент Y Combinator",
            "quote": "Переход к рассуждающим моделям и автономным ИИ-агентам приведет к появлению систем уровня AGI уже в ближайшие годы.",
            "socials": [
                {"platform": "x", "identifier": "@sama", "url": "https://x.com/sama", "title": "X: @sama"},
                {"platform": "youtube", "identifier": "OpenAI", "url": "https://www.youtube.com/@OpenAI", "title": "YouTube: OpenAI"},
                {"platform": "web", "identifier": "blog.samaltman.com", "url": "https://blog.samaltman.com", "title": "Blog: Sam Altman"}
            ],
            "predictions": [
                {"event_hypothesis": "ИИ-модели нового поколения достигнут уровня экспертного AGI в программировании и науке", "speaker_confidence": 0.89, "domain": "tech"}
            ]
        }
    ]

    @classmethod
    def get_curated_entry(cls, name: str) -> Optional[Dict[str, Any]]:
        if not name:
            return None
        clean = name.strip().lower()
        canonical = cls.NAME_ALIASES.get(clean, clean)
        for item in cls.CURATED_ANALYSTS:
            if item["name"].lower() == canonical or item["name"].lower() == clean:
                return item
        return None

    @classmethod
    def discover_socials_for_person(
        cls,
        name: str,
        handle_or_channel: Optional[str] = None,
        context_text: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """
        Discovers and returns all social networks (X/Twitter, YouTube, Telegram, Web)
        for a given analyst name. Uses curated profiles + extracted handles + smart search links.
        """
        if not name:
            return []

        socials: List[Dict[str, str]] = []
        curated = cls.get_curated_entry(name)
        if curated and curated.get("socials"):
            for s in curated["socials"]:
                socials.append(dict(s))

        # Parse handle_or_channel if provided
        if handle_or_channel:
            hc = handle_or_channel.strip()
            if "t.me/" in hc:
                slug = hc.split("t.me/")[-1].split("?")[0].strip("/@")
                if slug and not any(s["platform"] == "telegram" for s in socials):
                    socials.append({
                        "platform": "telegram",
                        "identifier": f"@{slug}",
                        "url": f"https://t.me/s/{slug}",
                        "title": f"Telegram: @{slug}"
                    })
            elif "youtube.com" in hc or "youtu.be" in hc:
                if not any(s["platform"] == "youtube" for s in socials):
                    socials.append({
                        "platform": "youtube",
                        "identifier": "YouTube",
                        "url": hc if hc.startswith("http") else f"https://{hc}",
                        "title": "YouTube канал"
                    })
            elif "x.com/" in hc or "twitter.com/" in hc:
                slug = hc.split(".com/")[-1].split("?")[0].strip("/@")
                if slug and not any(s["platform"] in ("x", "twitter") for s in socials):
                    socials.append({
                        "platform": "x",
                        "identifier": f"@{slug}",
                        "url": f"https://x.com/{slug}",
                        "title": f"X: @{slug}"
                    })
            elif hc.startswith("@"):
                slug = hc.lstrip("@").split()[0]
                if slug and not any(s["platform"] in ("x", "twitter") for s in socials):
                    socials.append({
                        "platform": "x",
                        "identifier": f"@{slug}",
                        "url": f"https://x.com/{slug}",
                        "title": f"X: @{slug}"
                    })

        # Extract any @handle from context_text
        if context_text:
            handles = re.findall(r'@([A-Za-z0-9_]{3,25})', context_text)
            for h in handles:
                if not any(s["platform"] in ("x", "twitter") for s in socials):
                    socials.append({
                        "platform": "x",
                        "identifier": f"@{h}",
                        "url": f"https://x.com/{h}",
                        "title": f"X: @{h}"
                    })
                    break

        encoded_name = urllib.parse.quote(name.strip())
        clean_slug = re.sub(r'[^A-Za-z0-9]', '', name.strip())

        # Guarantee X (Twitter) link
        if not any(s["platform"] in ("x", "twitter") for s in socials):
            if clean_slug and len(clean_slug) >= 4:
                socials.append({
                    "platform": "x",
                    "identifier": f"@{clean_slug}",
                    "url": f"https://x.com/search?q={encoded_name}&f=user",
                    "title": f"X: {name.strip()}"
                })
            else:
                socials.append({
                    "platform": "x",
                    "identifier": "X (Twitter)",
                    "url": f"https://x.com/search?q={encoded_name}",
                    "title": f"X: {name.strip()}"
                })

        # Guarantee YouTube link
        if not any(s["platform"] == "youtube" for s in socials):
            socials.append({
                "platform": "youtube",
                "identifier": "YouTube",
                "url": f"https://www.youtube.com/results?search_query={encoded_name}",
                "title": f"YouTube: {name.strip()}"
            })

        # Guarantee Telegram link
        if not any(s["platform"] == "telegram" for s in socials):
            socials.append({
                "platform": "telegram",
                "identifier": "Telegram",
                "url": f"https://t.me/s/{clean_slug.lower()}" if clean_slug and len(clean_slug) >= 4 else f"https://news.google.com/search?q={encoded_name}+telegram",
                "title": "Telegram"
            })

        # Guarantee Web / Media mentions link
        if not any(s["platform"] == "web" for s in socials):
            socials.append({
                "platform": "web",
                "identifier": "Google News",
                "url": f"https://news.google.com/search?q={encoded_name}",
                "title": "Упоминания в СМИ"
            })

        return socials
