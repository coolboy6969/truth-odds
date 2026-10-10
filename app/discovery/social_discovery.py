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
        },
        {
            "name": "Ki Young Ju",
            "domain": "crypto",
            "channel": "CryptoQuant",
            "bio": "Основатель и CEO аналитической платформы ончейн-данных CryptoQuant",
            "quote": "Приток капитала от институциональных кастодианов и ETF-фондов показывает, что киты продолжают агрессивную фазу накопления Bitcoin.",
            "socials": [
                {"platform": "x", "identifier": "@ki_young_ju", "url": "https://x.com/ki_young_ju", "title": "X: @ki_young_ju"},
                {"platform": "youtube", "identifier": "CryptoQuant", "url": "https://www.youtube.com/@CryptoQuant_official", "title": "YouTube: CryptoQuant"},
                {"platform": "web", "identifier": "cryptoquant.com", "url": "https://cryptoquant.com", "title": "Web: CryptoQuant"}
            ],
            "predictions": [
                {"event_hypothesis": "Реализованная капитализация Bitcoin обновит максимум благодаря институциональным притокам", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Michael Van Poppe",
            "domain": "crypto",
            "channel": "MN Consultancy",
            "bio": "Основатель и CIO инвестиционной компании MN Capital, технический и макро-криптоаналитик",
            "quote": "Ротация капитала из Bitcoin в экосистему Ethereum и инфраструктурные DeFi-протоколы ускорится на фоне снижения доходностей гособлигаций.",
            "socials": [
                {"platform": "x", "identifier": "@CryptoMichNL", "url": "https://x.com/CryptoMichNL", "title": "X: @CryptoMichNL"},
                {"platform": "youtube", "identifier": "Michael van de Poppe", "url": "https://www.youtube.com/@CryptoMichNL", "title": "YouTube: CryptoMichNL"},
                {"platform": "web", "identifier": "mncapital.vc", "url": "https://mncapital.vc", "title": "Web: MN Capital"}
            ],
            "predictions": [
                {"event_hypothesis": "Пара ETH/BTC развернется вверх и покажет рост более чем на 35%", "speaker_confidence": 0.79, "domain": "crypto"}
            ]
        },
        {
            "name": "Rekt Capital",
            "domain": "crypto",
            "channel": "Rekt Capital Research",
            "bio": "Ведущий исследователь рыночных циклов Bitcoin и технических паттернов халвинга",
            "quote": "Историческая структура циклов халвинга подтверждает выход из диапазона повторного накопления в фазу параболического тренда.",
            "socials": [
                {"platform": "x", "identifier": "@rektcapital", "url": "https://x.com/rektcapital", "title": "X: @rektcapital"},
                {"platform": "youtube", "identifier": "Rekt Capital", "url": "https://www.youtube.com/@RektCapital", "title": "YouTube: Rekt Capital"},
                {"platform": "web", "identifier": "rektcapital.substack.com", "url": "https://rektcapital.substack.com", "title": "Substack: Rekt Capital"}
            ],
            "predictions": [
                {"event_hypothesis": "Bitcoin войдет в фазу параболического ускорения после закрепления выше ключевого недельного сопротивления", "speaker_confidence": 0.83, "domain": "crypto"}
            ]
        },
        {
            "name": "James Check",
            "domain": "crypto",
            "channel": "Checkonchain",
            "bio": "Ведущий ончейн-аналитик Checkonchain (экс-главный аналитик Glassnode)",
            "quote": "Индикаторы MVRV и SOPR долгосрочных держателей сигнализируют о здоровой структуре бычьего рынка без признаков перегрева.",
            "socials": [
                {"platform": "x", "identifier": "@_Checkonchain", "url": "https://x.com/_Checkonchain", "title": "X: @_Checkonchain"},
                {"platform": "youtube", "identifier": "Checkonchain", "url": "https://www.youtube.com/@Checkonchain", "title": "YouTube: Checkonchain"},
                {"platform": "web", "identifier": "checkonchain.com", "url": "https://www.checkonchain.com", "title": "Web: Checkonchain"}
            ],
            "predictions": [
                {"event_hypothesis": "Ончейн-метрика MVRV достигнет зоны перегрева выше 3.2 перед вершиной цикла BTC", "speaker_confidence": 0.82, "domain": "crypto"}
            ]
        },
        {
            "name": "Jan Happel",
            "domain": "crypto",
            "channel": "Glassnode & Negentropic",
            "bio": "Сооснователь аналитической платформы Glassnode и фонда Swissblock",
            "quote": "Снижение индекса доллара DXY и рост глобальной ликвидности M2 создают идеальные макроусловия для ралли цифровых активов.",
            "socials": [
                {"platform": "x", "identifier": "@Negentropic_", "url": "https://x.com/Negentropic_", "title": "X: @Negentropic_"},
                {"platform": "youtube", "identifier": "Glassnode", "url": "https://www.youtube.com/@glassnode", "title": "YouTube: Glassnode"},
                {"platform": "web", "identifier": "glassnode.com", "url": "https://glassnode.com", "title": "Web: Glassnode"}
            ],
            "predictions": [
                {"event_hypothesis": "Ослабление индекса DXY ниже 100 пунктов запустит ралли рисковых активов и BTC", "speaker_confidence": 0.80, "domain": "crypto"}
            ]
        },
        {
            "name": "Chris Burniske",
            "domain": "crypto",
            "channel": "Placeholder VC",
            "bio": "Партнер венчурного фонда Placeholder, бывший руководитель крипто-направления ARK Invest",
            "quote": "Модульные блокчейны и децентрализованные сети физической инфраструктуры (DePIN) станут главными бенефициарами венчурного цикла.",
            "socials": [
                {"platform": "x", "identifier": "@cburniske", "url": "https://x.com/cburniske", "title": "X: @cburniske"},
                {"platform": "youtube", "identifier": "Chris Burniske", "url": "https://www.youtube.com/results?search_query=Chris+Burniske+Placeholder", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "placeholder.vc", "url": "https://www.placeholder.vc", "title": "Web: Placeholder VC"}
            ],
            "predictions": [
                {"event_hypothesis": "Капитализация сектора DePIN и AI-протоколов вырастет более чем в 3 раза", "speaker_confidence": 0.81, "domain": "crypto"}
            ]
        },
        {
            "name": "Haseeb Qureshi",
            "domain": "crypto",
            "channel": "Dragonfly Capital",
            "bio": "Управляющий партнер глобального крипто-венчурного фонда Dragonfly Capital",
            "quote": "Институционализация стейблкоинов и платежных блокчейн-шлюзов приведет к многократному росту транзакционных объемов в сети.",
            "socials": [
                {"platform": "x", "identifier": "@hosseeb", "url": "https://x.com/hosseeb", "title": "X: @hosseeb"},
                {"platform": "youtube", "identifier": "Chopping Block", "url": "https://www.youtube.com/results?search_query=Haseeb+Qureshi+Dragonfly", "title": "YouTube: Chopping Block"},
                {"platform": "web", "identifier": "dragonfly.xyz", "url": "https://www.dragonfly.xyz", "title": "Web: Dragonfly"}
            ],
            "predictions": [
                {"event_hypothesis": "Общая капитализация стейблкоинов превысит $300 млрд на фоне глобального платежного спроса", "speaker_confidence": 0.86, "domain": "crypto"}
            ]
        },
        {
            "name": "Anatoly Yakovenko",
            "domain": "crypto",
            "channel": "Solana Labs",
            "bio": "Сооснователь и CEO Solana Labs, инженер распределенных высокопроизводительных систем",
            "quote": "Единый глобальный стейт-машин на скорости света позволит децентрализованным биржам конкурировать с NASDAQ по задержкам и ликвидности.",
            "socials": [
                {"platform": "x", "identifier": "@aeyakovenko", "url": "https://x.com/aeyakovenko", "title": "X: @aeyakovenko"},
                {"platform": "youtube", "identifier": "Solana", "url": "https://www.youtube.com/@SolanaFndn", "title": "YouTube: Solana"},
                {"platform": "web", "identifier": "solana.com", "url": "https://solana.com", "title": "Web: Solana"}
            ],
            "predictions": [
                {"event_hypothesis": "Сеть Solana превысит показатель 100,000 TPS в основной сети после внедрения Firedancer", "speaker_confidence": 0.87, "domain": "crypto"}
            ]
        },
        {
            "name": "Hayden Adams",
            "domain": "crypto",
            "channel": "Uniswap Labs",
            "bio": "Основатель и CEO Uniswap Labs, создатель протокола автоматического маркет-мейкинга (AMM)",
            "quote": "Ончейн-ликвидность и кастомизируемые пулы Uniswap v4 вытеснят классические централизованные книги заявок на длинной дистанции.",
            "socials": [
                {"platform": "x", "identifier": "@haydenzadams", "url": "https://x.com/haydenzadams", "title": "X: @haydenzadams"},
                {"platform": "youtube", "identifier": "Uniswap", "url": "https://www.youtube.com/results?search_query=Hayden+Adams+Uniswap", "title": "YouTube: Uniswap"},
                {"platform": "web", "identifier": "uniswap.org", "url": "https://uniswap.org", "title": "Web: Uniswap"}
            ],
            "predictions": [
                {"event_hypothesis": "Доля торгов на децентрализованных биржах (DEX) превысит 25% от объема спотовых CEX", "speaker_confidence": 0.83, "domain": "crypto"}
            ]
        },
        {
            "name": "Stani Kulechov",
            "domain": "crypto",
            "channel": "Aave & Avara",
            "bio": "Основатель кредитного DeFi-протокола Aave и экосистемы Avara",
            "quote": "Интеграция реальных активов (RWA) и институциональных пулов ликвидности сделает DeFi базовой процентной ставкой интернета.",
            "socials": [
                {"platform": "x", "identifier": "@StaniKulechov", "url": "https://x.com/StaniKulechov", "title": "X: @StaniKulechov"},
                {"platform": "youtube", "identifier": "Aave", "url": "https://www.youtube.com/results?search_query=Stani+Kulechov+Aave", "title": "YouTube: Aave"},
                {"platform": "web", "identifier": "aave.com", "url": "https://aave.com", "title": "Web: Aave"}
            ],
            "predictions": [
                {"event_hypothesis": "Объем заблокированной ликвидности (TVL) в кредитных DeFi-протоколах обновит исторический максимум", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Rune Christensen",
            "domain": "crypto",
            "channel": "Sky (MakerDAO)",
            "bio": "Сооснователь MakerDAO (Sky), архитектор децентрализованных стейблкоинов и RWA-доходности",
            "quote": "Децентрализованные стейблкоины с встроенной доходностью от казначейских облигаций США привлекут десятки миллиардов институционального капитала.",
            "socials": [
                {"platform": "x", "identifier": "@RuneKek", "url": "https://x.com/RuneKek", "title": "X: @RuneKek"},
                {"platform": "youtube", "identifier": "Sky Ecosystem", "url": "https://www.youtube.com/results?search_query=Rune+Christensen+MakerDAO", "title": "YouTube: Выступления"},
                {"platform": "web", "identifier": "sky.money", "url": "https://sky.money", "title": "Web: Sky.money"}
            ],
            "predictions": [
                {"event_hypothesis": "Токенизированные казначейские облигации США (RWA) вырастут в объеме более чем в 2 раза за год", "speaker_confidence": 0.85, "domain": "crypto"}
            ]
        },
        {
            "name": "Matt Hougan",
            "domain": "crypto",
            "channel": "Bitwise Asset Management",
            "bio": "Директор по инвестициям (CIO) компании по управлению криптоактивами Bitwise",
            "quote": "Подключение крупных банковских платформ Morgan Stanley и Merrill Lynch к спотовым ETF обеспечит многолетний структурный приток капитала.",
            "socials": [
                {"platform": "x", "identifier": "@Matt_Hougan", "url": "https://x.com/Matt_Hougan", "title": "X: @Matt_Hougan"},
                {"platform": "youtube", "identifier": "Bitwise Invest", "url": "https://www.youtube.com/@BitwiseInvest", "title": "YouTube: Bitwise"},
                {"platform": "web", "identifier": "bitwiseinvestments.com", "url": "https://bitwiseinvestments.com", "title": "Web: Bitwise"}
            ],
            "predictions": [
                {"event_hypothesis": "Институциональные портфельные управляющие увеличат аллокацию в крипто-ETF до 3–5%", "speaker_confidence": 0.86, "domain": "crypto"}
            ]
        },
        {
            "name": "Eric Balchunas",
            "domain": "macro",
            "channel": "Bloomberg Intelligence",
            "bio": "Старший аналитик по биржевым фондам (ETF) в Bloomberg Intelligence",
            "quote": "Спотовые биткоин-ETF побили все исторические рекорды запусков биржевых фондов и приближаются по активам к золотым фондам.",
            "socials": [
                {"platform": "x", "identifier": "@EricBalchunas", "url": "https://x.com/EricBalchunas", "title": "X: @EricBalchunas"},
                {"platform": "youtube", "identifier": "Bloomberg Television", "url": "https://www.youtube.com/results?search_query=Eric+Balchunas+Bloomberg+ETF", "title": "YouTube: Bloomberg ETF"},
                {"platform": "web", "identifier": "bloomberg.com", "url": "https://www.bloomberg.com", "title": "Web: Bloomberg"}
            ],
            "predictions": [
                {"event_hypothesis": "Суммарные активы спотовых Bitcoin ETF в США превысят совокупный объем золотых ETF", "speaker_confidence": 0.85, "domain": "crypto"}
            ]
        },
        {
            "name": "James Seyffart",
            "domain": "crypto",
            "channel": "Bloomberg Intelligence",
            "bio": "Аналитик по исследованию рынка ETF и регуляторной политики SEC в Bloomberg Intelligence",
            "quote": "Одобрение новых крипто-ETF и опционов на спотовые фонды радикально углубляет институциональную ликвидность рынка.",
            "socials": [
                {"platform": "x", "identifier": "@JSeyff", "url": "https://x.com/JSeyff", "title": "X: @JSeyff"},
                {"platform": "youtube", "identifier": "James Seyffart", "url": "https://www.youtube.com/results?search_query=James+Seyffart+Bloomberg", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "bloomberg.com", "url": "https://www.bloomberg.com", "title": "Web: Bloomberg"}
            ],
            "predictions": [
                {"event_hypothesis": "SEC одобрит запуск новых спотовых крипто-ETF на ведущие альткоины (SOL, XRP)", "speaker_confidence": 0.82, "domain": "crypto"}
            ]
        },
        {
            "name": "Alex Thorn",
            "domain": "crypto",
            "channel": "Galaxy Digital Research",
            "bio": "Глава общекорпоративных исследований в инвестиционном банке Galaxy Digital",
            "quote": "Позиционирование маркет-мейкеров на рынке крипто-опционов указывает на сжатие гаммы и ускорение восходящего импульса.",
            "socials": [
                {"platform": "x", "identifier": "@intangiblecoins", "url": "https://x.com/intangiblecoins", "title": "X: @intangiblecoins"},
                {"platform": "youtube", "identifier": "Galaxy Digital", "url": "https://www.youtube.com/results?search_query=Alex+Thorn+Galaxy+Research", "title": "YouTube: Galaxy Research"},
                {"platform": "web", "identifier": "galaxy.com/research", "url": "https://www.galaxy.com/insights/research/", "title": "Web: Galaxy Research"}
            ],
            "predictions": [
                {"event_hypothesis": "Суверенные фонды и корпоративные казначейства добавят Bitcoin на баланс в течение года", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Mike Novogratz",
            "domain": "macro",
            "channel": "Galaxy Digital",
            "bio": "Основатель и CEO инвестиционной группы Galaxy Digital, бывший партнер Fortress Investment",
            "quote": "В условиях беспрецедентного роста госдолга США и геополитической фрагментации твердые активы вроде золота и BTC неизбежно дорожают.",
            "socials": [
                {"platform": "x", "identifier": "@novogratz", "url": "https://x.com/novogratz", "title": "X: @novogratz"},
                {"platform": "youtube", "identifier": "CNBC / Galaxy", "url": "https://www.youtube.com/results?search_query=Mike+Novogratz+CNBC", "title": "YouTube: CNBC Интервью"},
                {"platform": "web", "identifier": "galaxy.com", "url": "https://www.galaxy.com", "title": "Web: Galaxy Digital"}
            ],
            "predictions": [
                {"event_hypothesis": "Bitcoin закрепится выше $120,000 на фоне смягчения монетарной политики ФРС", "speaker_confidence": 0.83, "domain": "crypto"}
            ]
        },
        {
            "name": "Dan Morehead",
            "domain": "crypto",
            "channel": "Pantera Capital",
            "bio": "Основатель и управляющий партнер старейшего крипто-хедж-фонда США Pantera Capital",
            "quote": "Блокчейн-активы демонстрируют многолетний экспоненциальный тренд принятия, аналогичный развитию интернета в 1990-х годах.",
            "socials": [
                {"platform": "x", "identifier": "@dan_pantera", "url": "https://x.com/dan_pantera", "title": "X: @dan_pantera"},
                {"platform": "youtube", "identifier": "Pantera Capital", "url": "https://www.youtube.com/results?search_query=Dan+Morehead+Pantera", "title": "YouTube: Pantera"},
                {"platform": "web", "identifier": "panteracapital.com", "url": "https://panteracapital.com", "title": "Web: Pantera Letters"}
            ],
            "predictions": [
                {"event_hypothesis": "Институциональная капитализация крипторынка вырастет более чем в 2 раза за текущий цикл", "speaker_confidence": 0.85, "domain": "crypto"}
            ]
        },
        {
            "name": "Tuur Demeester",
            "domain": "crypto",
            "channel": "Adamant Research",
            "bio": "Главный редактор Adamant Research, ранний биткоин-экономист и инвестор с 2012 года",
            "quote": "Биткоин превращается в глобальный расчетный слой и страховой полис против монетарной инфляции центральных банков.",
            "socials": [
                {"platform": "x", "identifier": "@TuurDemeester", "url": "https://x.com/TuurDemeester", "title": "X: @TuurDemeester"},
                {"platform": "youtube", "identifier": "Tuur Demeester", "url": "https://www.youtube.com/results?search_query=Tuur+Demeester+Bitcoin", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "adamantresearch.com", "url": "https://adamantresearch.com", "title": "Web: Adamant Research"}
            ],
            "predictions": [
                {"event_hypothesis": "Bitcoin продолжит опережать золото по среднегодовой доходности", "speaker_confidence": 0.84, "domain": "crypto"}
            ]
        },
        {
            "name": "Preston Pysh",
            "domain": "macro",
            "channel": "The Investor's Podcast",
            "bio": "Сооснователь The Investor's Podcast Network, эксперт по макроэкономике и долговым рынкам",
            "quote": "Суверенный долговой кризис вынудит центробанки выкупать казначейские облигации, увеличивая денежную массу и стоимость реальных активов.",
            "socials": [
                {"platform": "x", "identifier": "@PrestonPysh", "url": "https://x.com/PrestonPysh", "title": "X: @PrestonPysh"},
                {"platform": "youtube", "identifier": "We Study Billionaires", "url": "https://www.youtube.com/@WeStudyBillionaires", "title": "YouTube: TIP Network"},
                {"platform": "web", "identifier": "theinvestorspodcast.com", "url": "https://www.theinvestorspodcast.com", "title": "Web: TIP Network"}
            ],
            "predictions": [
                {"event_hypothesis": "ФРС вернется к расширению баланса для стабилизации рынка казначейского долга", "speaker_confidence": 0.81, "domain": "macro"}
            ]
        },
        {
            "name": "Murad Mahmudov",
            "domain": "crypto",
            "channel": "Adaptive Analysis",
            "bio": "Криптовалютный аналитик и инвестор, выпускник Принстона, исследователь токеномики и сообществ",
            "quote": "Токены с сильными децентрализованными сообществами и высокой вовлеченностью розничных участников демонстрируют максимальный сетевой эффект.",
            "socials": [
                {"platform": "x", "identifier": "@MustStopMurad", "url": "https://x.com/MustStopMurad", "title": "X: @MustStopMurad"},
                {"platform": "youtube", "identifier": "Murad Mahmudov", "url": "https://www.youtube.com/results?search_query=Murad+Mahmudov+crypto", "title": "YouTube: Лекции и обзоры"},
                {"platform": "web", "identifier": "x.com/MustStopMurad", "url": "https://x.com/MustStopMurad", "title": "Web: Профиль"}
            ],
            "predictions": [
                {"event_hypothesis": "Розничные крипто-активы с высокой концентрацией холдеров покажут опережающую динамику в пиковой фазе цикла", "speaker_confidence": 0.78, "domain": "crypto"}
            ]
        },
        {
            "name": "Arthur Cheong",
            "domain": "crypto",
            "channel": "DeFiance Capital",
            "bio": "Основатель и инвестиционный директор криптофонда DeFiance Capital",
            "quote": "Фундаментально прибыльные DeFi-протоколы с реальным денежным потоком и байбэками токенов возглавят следующую волну институционального спроса.",
            "socials": [
                {"platform": "x", "identifier": "@Arthur_0x", "url": "https://x.com/Arthur_0x", "title": "X: @Arthur_0x"},
                {"platform": "youtube", "identifier": "DeFiance Capital", "url": "https://www.youtube.com/results?search_query=Arthur+Cheong+DeFiance", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "defiance.capital", "url": "https://defiance.capital", "title": "Web: DeFiance Capital"}
            ],
            "predictions": [
                {"event_hypothesis": "DeFi-протоколы с распределением комиссии холдерам увеличат капитализацию более чем в 2 раза", "speaker_confidence": 0.80, "domain": "crypto"}
            ]
        },
        {
            "name": "Brian Armstrong",
            "domain": "crypto",
            "channel": "Coinbase",
            "bio": "Сооснователь и CEO крупнейшей публичной криптобиржи США Coinbase",
            "quote": "Принятие четкого законодательства о рыночной структуре и стейблкоинах в США откроет путь для перевода классических финансов на блокчейн-рельсы.",
            "socials": [
                {"platform": "x", "identifier": "@brian_armstrong", "url": "https://x.com/brian_armstrong", "title": "X: @brian_armstrong"},
                {"platform": "youtube", "identifier": "Coinbase", "url": "https://www.youtube.com/@coinbase", "title": "YouTube: Coinbase"},
                {"platform": "web", "identifier": "coinbase.com/blog", "url": "https://www.coinbase.com/blog", "title": "Web: Coinbase Blog"}
            ],
            "predictions": [
                {"event_hypothesis": "Конгресс США примет федеральный закон о регулировании стейблкоинов и крипторынка", "speaker_confidence": 0.85, "domain": "crypto"}
            ]
        },
        {
            "name": "Paolo Ardoino",
            "domain": "crypto",
            "channel": "Tether & Bitfinex",
            "bio": "CEO эмитента крупнейшего стейблкоина Tether (USDT) и технический директор Bitfinex",
            "quote": "Цифровой доллар на блокчейне стал главным платежным инструментом развивающихся рынков, а резервы Tether в казначейских бондах США превышают показатели многих стран.",
            "socials": [
                {"platform": "x", "identifier": "@paoloardoino", "url": "https://x.com/paoloardoino", "title": "X: @paoloardoino"},
                {"platform": "youtube", "identifier": "Paolo Ardoino", "url": "https://www.youtube.com/results?search_query=Paolo+Ardoino+Tether", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "tether.to", "url": "https://tether.to", "title": "Web: Tether"}
            ],
            "predictions": [
                {"event_hypothesis": "Рыночная капитализация USDT превысит $180 млрд за счет спроса в развивающихся странах", "speaker_confidence": 0.86, "domain": "crypto"}
            ]
        },
        {
            "name": "Brad Garlinghouse",
            "domain": "crypto",
            "channel": "Ripple",
            "bio": "Генеральный директор финтех-компании Ripple, эксперт по трансграничным блокчейн-платежам",
            "quote": "Снятие регуляторных барьеров в США и запуск институциональных стейблкоинов ускорят внедрение блокчейна в межбанковские расчеты.",
            "socials": [
                {"platform": "x", "identifier": "@bgarlinghouse", "url": "https://x.com/bgarlinghouse", "title": "X: @bgarlinghouse"},
                {"platform": "youtube", "identifier": "Ripple", "url": "https://www.youtube.com/@Ripple", "title": "YouTube: Ripple"},
                {"platform": "web", "identifier": "ripple.com", "url": "https://ripple.com", "title": "Web: Ripple"}
            ],
            "predictions": [
                {"event_hypothesis": "Институциональное внедрение трансграничных крипто-расчетов увеличит капитализацию XRP и платежных токенов", "speaker_confidence": 0.79, "domain": "crypto"}
            ]
        },
        {
            "name": "Charles Hoskinson",
            "domain": "crypto",
            "channel": "Input Output (Cardano)",
            "bio": "Основатель блокчейн-платформы Cardano и исследовательской компании Input Output Global",
            "quote": "Децентрализованное ончейн-управление и формальная верификация смарт-контрактов станут стандартом для государственных и финансовых блокчейн-систем.",
            "socials": [
                {"platform": "x", "identifier": "@IOHK_Charles", "url": "https://x.com/IOHK_Charles", "title": "X: @IOHK_Charles"},
                {"platform": "youtube", "identifier": "Charles Hoskinson", "url": "https://www.youtube.com/@charleshoskinsoncrypto", "title": "YouTube: Charles Hoskinson"},
                {"platform": "web", "identifier": "iohk.io", "url": "https://iohk.io", "title": "Web: IOHK"}
            ],
            "predictions": [
                {"event_hypothesis": "Блокчейн-протоколы с децентрализованным казначейством привлекут государственные пилотные проекты", "speaker_confidence": 0.76, "domain": "crypto"}
            ]
        },
        {
            "name": "Sandeep Nailwal",
            "domain": "crypto",
            "channel": "Polygon Labs",
            "bio": "Сооснователь экосистемы масштабирования Polygon и венчурного акселератора Symbolic Capital",
            "quote": "Технология доказательств с нулевым разглашением (ZK-proofs) и агрегация ликвидности объединят разрозненные L2-сети в единое пространство.",
            "socials": [
                {"platform": "x", "identifier": "@sandeepnailwal", "url": "https://x.com/sandeepnailwal", "title": "X: @sandeepnailwal"},
                {"platform": "youtube", "identifier": "Polygon Labs", "url": "https://www.youtube.com/@PolygonTV", "title": "YouTube: Polygon"},
                {"platform": "web", "identifier": "polygon.technology", "url": "https://polygon.technology", "title": "Web: Polygon"}
            ],
            "predictions": [
                {"event_hypothesis": "ZK-роллапы займут более половины рынка масштабирования второго уровня Ethereum", "speaker_confidence": 0.80, "domain": "crypto"}
            ]
        },
        {
            "name": "Ray Dalio",
            "domain": "macro",
            "channel": "Bridgewater Associates",
            "bio": "Основатель крупнейшего в мире хедж-фонда Bridgewater Associates, автор теории больших долговых циклов",
            "quote": "США находятся на поздней стадии долгосрочного долгового цикла: монетизация дефицита ослабит фиатные валюты по отношению к золоту и реальным активам.",
            "socials": [
                {"platform": "x", "identifier": "@RayDalio", "url": "https://x.com/RayDalio", "title": "X: @RayDalio"},
                {"platform": "youtube", "identifier": "Principles by Ray Dalio", "url": "https://www.youtube.com/@principlesbyraydalio", "title": "YouTube: Ray Dalio"},
                {"platform": "web", "identifier": "principles.com", "url": "https://www.principles.com", "title": "Web: Principles"}
            ],
            "predictions": [
                {"event_hypothesis": "Рост расходов на обслуживание госдолга США приведет к девальвации доллара относительно золота", "speaker_confidence": 0.86, "domain": "macro"}
            ]
        },
        {
            "name": "Stanley Druckenmiller",
            "domain": "macro",
            "channel": "Duquesne Family Office",
            "bio": "Легендарный макро-инвестор, глава Duquesne Family Office со среднегодовой доходностью 30% за три десятилетия",
            "quote": "Искусственный интеллект представляет собой мегатренд масштаба интернета, однако раздутый бюджетный дефицит США несет риски новой волны инфляции.",
            "socials": [
                {"platform": "x", "identifier": "@Druckenmiller", "url": "https://x.com/search?q=Stanley+Druckenmiller", "title": "X: Stanley Druckenmiller"},
                {"platform": "youtube", "identifier": "CNBC / Norges Bank", "url": "https://www.youtube.com/results?search_query=Stanley+Druckenmiller+interview", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "bloomberg.com", "url": "https://www.bloomberg.com", "title": "Web: Упоминания в СМИ"}
            ],
            "predictions": [
                {"event_hypothesis": "Доходность 10-летних казначейских облигаций США сохранит повышенную волатильность из-за бюджетного дефицита", "speaker_confidence": 0.84, "domain": "macro"}
            ]
        },
        {
            "name": "Paul Tudor Jones",
            "domain": "macro",
            "channel": "Tudor Investment Corp",
            "bio": "Основатель макро-фонда Tudor Investment Corporation, миллиардер и пионер глобального макро-трейдинга",
            "quote": "Все дороги ведут к инфляции: единственный способ справиться с долговой нагрузкой развитых стран — обесценение валюты, поэтому я держу золото, BTC и сырье.",
            "socials": [
                {"platform": "x", "identifier": "@ptj_official", "url": "https://x.com/search?q=Paul+Tudor+Jones", "title": "X: Paul Tudor Jones"},
                {"platform": "youtube", "identifier": "CNBC Squawk Box", "url": "https://www.youtube.com/results?search_query=Paul+Tudor+Jones+CNBC", "title": "YouTube: CNBC Интервью"},
                {"platform": "web", "identifier": "tudor.com", "url": "https://www.cnbc.com", "title": "Web: CNBC Macro"}
            ],
            "predictions": [
                {"event_hypothesis": "Инфляционные активы (золото, Bitcoin, сырьевой индекс) опередят государственные облигации США", "speaker_confidence": 0.87, "domain": "macro"}
            ]
        },
        {
            "name": "Bill Ackman",
            "domain": "macro",
            "channel": "Pershing Square Capital",
            "bio": "Основатель и CEO хедж-фонда Pershing Square Capital Management, активист-инвестор",
            "quote": "Корпоративный сектор США с высокой маржинальностью и внедрением ИИ продолжит генерировать рекордный свободный денежный поток.",
            "socials": [
                {"platform": "x", "identifier": "@BillAckman", "url": "https://x.com/BillAckman", "title": "X: @BillAckman"},
                {"platform": "youtube", "identifier": "Bill Ackman", "url": "https://www.youtube.com/results?search_query=Bill+Ackman+Pershing+Square", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "pershingsquareholdings.com", "url": "https://pershingsquareholdings.com", "title": "Web: Pershing Square"}
            ],
            "predictions": [
                {"event_hypothesis": "Крупнейшие американские компании технологического и инфраструктурного сектора увеличат чистую прибыль", "speaker_confidence": 0.81, "domain": "macro"}
            ]
        },
        {
            "name": "Howard Marks",
            "domain": "macro",
            "channel": "Oaktree Capital Management",
            "bio": "Сопредседатель Oaktree Capital Management, автор знаменитых инвестиционных меморандумов о рыночных циклах",
            "quote": "Мы живем в эпоху фундаментальной смены режима процентных ставок: эпоха бесплатных денег около нуля ушла в прошлое.",
            "socials": [
                {"platform": "x", "identifier": "@Oaktree", "url": "https://x.com/search?q=Howard+Marks+Oaktree", "title": "X: Howard Marks"},
                {"platform": "youtube", "identifier": "Oaktree Capital", "url": "https://www.youtube.com/@oaktreecapital", "title": "YouTube: Oaktree"},
                {"platform": "web", "identifier": "oaktreecapital.com/insights", "url": "https://www.oaktreecapital.com/insights", "title": "Web: Memos by Howard Marks"}
            ],
            "predictions": [
                {"event_hypothesis": "Базовая ставка ФРС останется в диапазоне выше 3% на среднесрочном горизонте", "speaker_confidence": 0.85, "domain": "macro"}
            ]
        },
        {
            "name": "Mohamed El-Erian",
            "domain": "macro",
            "channel": "Allianz & Wharton",
            "bio": "Главный экономический советник Allianz, президент Queens' College в Кембридже, экс-CEO PIMCO",
            "quote": "Дивергенция темпов экономического роста между США и Еврозоной приведет к разной траектории снижения ставок ЕЦБ и ФРС.",
            "socials": [
                {"platform": "x", "identifier": "@elerianm", "url": "https://x.com/elerianm", "title": "X: @elerianm"},
                {"platform": "youtube", "identifier": "Bloomberg / CNBC", "url": "https://www.youtube.com/results?search_query=Mohamed+El-Erian+Bloomberg", "title": "YouTube: Выступления"},
                {"platform": "web", "identifier": "mohamedelerian.com", "url": "https://www.bloomberg.com/opinion", "title": "Web: Колонка в Bloomberg"}
            ],
            "predictions": [
                {"event_hypothesis": "ЕЦБ проведет более глубокое снижение процентных ставок по сравнению с ФРС США", "speaker_confidence": 0.84, "domain": "macro"}
            ]
        },
        {
            "name": "Nouriel Roubini",
            "domain": "macro",
            "channel": "Roubini Macro Associates",
            "bio": "Профессор экономики NYU Stern, CEO Roubini Macro Associates, предсказавший кризис 2008 года",
            "quote": "Сочетание геополитических шоков, протекционистских тарифов и огромных суверенных долгов повышает риск стагфляционных сценариев.",
            "socials": [
                {"platform": "x", "identifier": "@Nouriel", "url": "https://x.com/Nouriel", "title": "X: @Nouriel"},
                {"platform": "youtube", "identifier": "Nouriel Roubini", "url": "https://www.youtube.com/results?search_query=Nouriel+Roubini+economy", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "roubini.com", "url": "https://www.project-syndicate.org", "title": "Web: Project Syndicate"}
            ],
            "predictions": [
                {"event_hypothesis": "Торговые тарифы и дефицит бюджета удержат инфляцию в развитых странах выше целевых 2%", "speaker_confidence": 0.80, "domain": "macro"}
            ]
        },
        {
            "name": "Ed Yardeni",
            "domain": "macro",
            "channel": "Yardeni Research",
            "bio": "Президент Yardeni Research, ветеран Уолл-стрит с 45-летним стажем макроэкономического прогнозирования",
            "quote": "Сценарий «Ревущих 2020-х» основан на буме производительности труда благодаря автоматизации и инвестициям в ИИ-инфраструктуру.",
            "socials": [
                {"platform": "x", "identifier": "@yardeni", "url": "https://x.com/yardeni", "title": "X: @yardeni"},
                {"platform": "youtube", "identifier": "Yardeni Research", "url": "https://www.youtube.com/results?search_query=Ed+Yardeni+CNBC", "title": "YouTube: Yardeni"},
                {"platform": "web", "identifier": "yardeni.com", "url": "https://www.yardeni.com", "title": "Web: Yardeni Research"}
            ],
            "predictions": [
                {"event_hypothesis": "Рост производительности труда позволит индексу S&P 500 продолжить многолетний бычий тренд", "speaker_confidence": 0.83, "domain": "macro"}
            ]
        },
        {
            "name": "Jeremy Siegel",
            "domain": "macro",
            "channel": "Wharton School",
            "bio": "Почетный профессор финансов Уортонской школы бизнеса, автор классической книги «Акции в долгосрочной перспективе»",
            "quote": "Акции остаются лучшим инструментом защиты от умеренной инфляции, а нормализация кривой доходности поддержит широкий рынок.",
            "socials": [
                {"platform": "x", "identifier": "@Wharton", "url": "https://x.com/search?q=Jeremy+Siegel+Wharton", "title": "X: Jeremy Siegel"},
                {"platform": "youtube", "identifier": "CNBC / WisdomTree", "url": "https://www.youtube.com/results?search_query=Jeremy+Siegel+CNBC", "title": "YouTube: CNBC"},
                {"platform": "web", "identifier": "wisdomtree.com", "url": "https://www.wisdomtree.com", "title": "Web: WisdomTree Commentary"}
            ],
            "predictions": [
                {"event_hypothesis": "Реальная доходность американских акций превысит доходность казначейских облигаций", "speaker_confidence": 0.82, "domain": "macro"}
            ]
        },
        {
            "name": "David Rosenberg",
            "domain": "macro",
            "channel": "Rosenberg Research",
            "bio": "Основатель и президент Rosenberg Research, бывший главный экономист Merrill Lynch по Северной Америке",
            "quote": "Охлаждение рынка труда и исчерпание избыточных сбережений домохозяйств указывают на замедление потребительского спроса.",
            "socials": [
                {"platform": "x", "identifier": "@EconguyRosie", "url": "https://x.com/EconguyRosie", "title": "X: @EconguyRosie"},
                {"platform": "youtube", "identifier": "Rosenberg Research", "url": "https://www.youtube.com/@RosenbergResearch", "title": "YouTube: Rosenberg"},
                {"platform": "web", "identifier": "rosenbergresearch.com", "url": "https://www.rosenbergresearch.com", "title": "Web: Rosenberg Research"}
            ],
            "predictions": [
                {"event_hypothesis": "Охлаждение рынка труда США вынудит ФРС ускорить снижение процентной ставки", "speaker_confidence": 0.78, "domain": "macro"}
            ]
        },
        {
            "name": "Luke Gromen",
            "domain": "macro",
            "channel": "Forest for the Trees (FFTT)",
            "bio": "Основатель макроэкономической исследовательской компании FFTT, специалист по суверенным долгам и ликвидности",
            "quote": "Фискальное доминирование в США означает, что баланс ФРС и ликвидность казначейства станут главными драйверами роста золота и Bitcoin.",
            "socials": [
                {"platform": "x", "identifier": "@LukeGromen", "url": "https://x.com/LukeGromen", "title": "X: @LukeGromen"},
                {"platform": "youtube", "identifier": "Luke Gromen", "url": "https://www.youtube.com/results?search_query=Luke+Gromen+macro", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "fftt-llc.com", "url": "https://fftt-llc.com", "title": "Web: FFTT LLC"}
            ],
            "predictions": [
                {"event_hypothesis": "Центральные банки развивающихся стран продолжат рекордные закупки золота в резервы", "speaker_confidence": 0.87, "domain": "macro"}
            ]
        },
        {
            "name": "Jim Bianco",
            "domain": "macro",
            "channel": "Bianco Research",
            "bio": "Президент макроаналитической компании Bianco Research, эксперт по рынку облигаций и монетарной политике",
            "quote": "Структурные изменения в цепочках поставок и деглобализация удерживают нейтральную процентную ставку выше уровней прошлого десятилетия.",
            "socials": [
                {"platform": "x", "identifier": "@biancoresearch", "url": "https://x.com/biancoresearch", "title": "X: @biancoresearch"},
                {"platform": "youtube", "identifier": "Bianco Research", "url": "https://www.youtube.com/@BiancoResearch", "title": "YouTube: Bianco Research"},
                {"platform": "web", "identifier": "biancoresearch.com", "url": "https://www.biancoresearch.com", "title": "Web: Bianco Research"}
            ],
            "predictions": [
                {"event_hypothesis": "Доходность 10-летних трежерис США протестирует отметку 4.5% на фоне крупных размещений госдолга", "speaker_confidence": 0.81, "domain": "macro"}
            ]
        },
        {
            "name": "Alfonso Peccatiello",
            "domain": "macro",
            "channel": "The Macro Compass",
            "bio": "Основатель The Macro Compass, бывший глава инвестиционного портфеля на $20 млрд в ING Germany",
            "quote": "Кредитный импульс и динамика банковских резервов определяют разворотные точки для глобальных индексов задолго до официальной статистики.",
            "socials": [
                {"platform": "x", "identifier": "@MacroAlf", "url": "https://x.com/MacroAlf", "title": "X: @MacroAlf"},
                {"platform": "youtube", "identifier": "The Macro Compass", "url": "https://www.youtube.com/@TheMacroCompass", "title": "YouTube: MacroAlf"},
                {"platform": "web", "identifier": "themacrocompass.com", "url": "https://www.themacrocompass.com", "title": "Web: Macro Compass"}
            ],
            "predictions": [
                {"event_hypothesis": "Спред доходности между гособлигациями США и Германии расширится из-за слабости экономики ЕС", "speaker_confidence": 0.80, "domain": "macro"}
            ]
        },
        {
            "name": "Brent Johnson",
            "domain": "macro",
            "channel": "Santiago Capital",
            "bio": "CEO инвестиционной компании Santiago Capital, автор макроэкономической теории «Dollar Milkshake Theory»",
            "quote": "Дефицит долларовой ликвидности за пределами США приводит к одновременному укреплению доллара против мировых валют и росту золота.",
            "socials": [
                {"platform": "x", "identifier": "@SantiagoAuFund", "url": "https://x.com/SantiagoAuFund", "title": "X: @SantiagoAuFund"},
                {"platform": "youtube", "identifier": "Milkshakes Markets", "url": "https://www.youtube.com/results?search_query=Brent+Johnson+Dollar+Milkshake", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "santiagocapital.com", "url": "https://santiagocapital.com", "title": "Web: Santiago Capital"}
            ],
            "predictions": [
                {"event_hypothesis": "Золото обновит исторический максимум одновременно в долларах, евро и иенах", "speaker_confidence": 0.85, "domain": "macro"}
            ]
        },
        {
            "name": "Larry Fink",
            "domain": "macro",
            "channel": "BlackRock",
            "bio": "Председатель и CEO крупнейшей в мире инвестиционной компании BlackRock ($11+ трлн под управлением)",
            "quote": "Токенизация финансовых активов и ценных бумаг на блокчейне станет следующей технологической революцией для рынков капитала.",
            "socials": [
                {"platform": "x", "identifier": "@BlackRock", "url": "https://x.com/BlackRock", "title": "X: @BlackRock"},
                {"platform": "youtube", "identifier": "BlackRock", "url": "https://www.youtube.com/@blackrock", "title": "YouTube: BlackRock"},
                {"platform": "web", "identifier": "blackrock.com", "url": "https://www.blackrock.com", "title": "Web: BlackRock Letters"}
            ],
            "predictions": [
                {"event_hypothesis": "Рынок токенизированных фондов и облигаций вырастет в разы с участием крупнейших УК Уолл-стрит", "speaker_confidence": 0.89, "domain": "crypto"}
            ]
        },
        {
            "name": "Jensen Huang",
            "domain": "tech",
            "channel": "NVIDIA",
            "bio": "Сооснователь, президент и CEO корпорации NVIDIA, лидер мировой индустрии ИИ-вычислений",
            "quote": "Мировая IT-инфраструктура стоимостью в триллионы долларов переходит от классических вычислений к ускоренным фабрикам искусственного интеллекта.",
            "socials": [
                {"platform": "x", "identifier": "@nvidia", "url": "https://x.com/nvidia", "title": "X: @nvidia"},
                {"platform": "youtube", "identifier": "NVIDIA", "url": "https://www.youtube.com/@NVIDIA", "title": "YouTube: NVIDIA"},
                {"platform": "web", "identifier": "nvidia.com", "url": "https://www.nvidia.com", "title": "Web: NVIDIA"}
            ],
            "predictions": [
                {"event_hypothesis": "Капитальные затраты (CapEx) мировых облачных гигантов на ИИ-дата-центры превысят $300 млрд в год", "speaker_confidence": 0.91, "domain": "tech"}
            ]
        },
        {
            "name": "Dario Amodei",
            "domain": "tech",
            "channel": "Anthropic",
            "bio": "Сооснователь и CEO исследовательской ИИ-компании Anthropic (создатели моделей Claude)",
            "quote": "Масштабирование вычислений и обучение с подкреплением позволят ИИ-системам совершать прорывы в биологии, медицине и инженерии.",
            "socials": [
                {"platform": "x", "identifier": "@DarioAmodei", "url": "https://x.com/DarioAmodei", "title": "X: @DarioAmodei"},
                {"platform": "youtube", "identifier": "Anthropic", "url": "https://www.youtube.com/@anthropic-ai", "title": "YouTube: Anthropic"},
                {"platform": "web", "identifier": "darioamodei.com", "url": "https://darioamodei.com", "title": "Web: Эссе Dario Amodei"}
            ],
            "predictions": [
                {"event_hypothesis": "Автономные ИИ-агенты возьмут на себя более половины задач по написанию и тестированию кода в крупных IT-компаниях", "speaker_confidence": 0.88, "domain": "tech"}
            ]
        },
        {
            "name": "Demis Hassabis",
            "domain": "tech",
            "channel": "Google DeepMind",
            "bio": "Сооснователь и CEO Google DeepMind, лауреат Нобелевской премии за прорывы в ИИ-моделировании белков",
            "quote": "ИИ-модели научного открытия сократят сроки разработки новых лекарственных препаратов и материалов с десятилетий до нескольких месяцев.",
            "socials": [
                {"platform": "x", "identifier": "@demishassabis", "url": "https://x.com/demishassabis", "title": "X: @demishassabis"},
                {"platform": "youtube", "identifier": "Google DeepMind", "url": "https://www.youtube.com/@GoogleDeepMind", "title": "YouTube: DeepMind"},
                {"platform": "web", "identifier": "deepmind.google", "url": "https://deepmind.google", "title": "Web: Google DeepMind"}
            ],
            "predictions": [
                {"event_hypothesis": "Первые клинические препараты, полностью спроектированные с помощью ИИ, успешно пройдут испытания", "speaker_confidence": 0.87, "domain": "tech"}
            ]
        },
        {
            "name": "Andrej Karpathy",
            "domain": "tech",
            "channel": "Eureka Labs",
            "bio": "Основатель Eureka Labs, бывший директор по ИИ в Tesla и сооснователь исследовательской группы OpenAI",
            "quote": "Большие языковые модели превращаются в новую операционную систему, где главным языком программирования становится естественный язык.",
            "socials": [
                {"platform": "x", "identifier": "@karpathy", "url": "https://x.com/karpathy", "title": "X: @karpathy"},
                {"platform": "youtube", "identifier": "Andrej Karpathy", "url": "https://www.youtube.com/@AndrejKarpathy", "title": "YouTube: Andrej Karpathy"},
                {"platform": "web", "identifier": "karpathy.ai", "url": "https://karpathy.ai", "title": "Web: karpathy.ai"}
            ],
            "predictions": [
                {"event_hypothesis": "Локальные мультимодальные ИИ-модели будут работать автономно на большинстве флагманских устройств", "speaker_confidence": 0.86, "domain": "tech"}
            ]
        },
        {
            "name": "Yann LeCun",
            "domain": "tech",
            "channel": "Meta AI & NYU",
            "bio": "Главный научный сотрудник по ИИ в Meta, профессор NYU, лауреат премии Тьюринга",
            "quote": "Открытые весовые модели (Open-Source AI) и архитектуры с моделью физического мира станут фундаментом глобальной ИИ-экосистемы.",
            "socials": [
                {"platform": "x", "identifier": "@ylecun", "url": "https://x.com/ylecun", "title": "X: @ylecun"},
                {"platform": "youtube", "identifier": "Yann LeCun", "url": "https://www.youtube.com/results?search_query=Yann+LeCun+AI", "title": "YouTube: Лекции"},
                {"platform": "web", "identifier": "ai.meta.com", "url": "https://ai.meta.com", "title": "Web: Meta AI"}
            ],
            "predictions": [
                {"event_hypothesis": "Открытые (open-source) ИИ-модели сравняются по качеству с закрытыми коммерческими системами", "speaker_confidence": 0.85, "domain": "tech"}
            ]
        },
        {
            "name": "Marc Andreessen",
            "domain": "tech",
            "channel": "Andreessen Horowitz (a16z)",
            "bio": "Сооснователь венчурного фонда Andreessen Horowitz (a16z) и браузера Netscape, автор «Манифеста технооптимиста»",
            "quote": "Симбиоз искусственного интеллекта, робототехники и децентрализованных сетей обеспечит беспрецедентный скачок экономического роста.",
            "socials": [
                {"platform": "x", "identifier": "@pmarca", "url": "https://x.com/pmarca", "title": "X: @pmarca"},
                {"platform": "youtube", "identifier": "a16z", "url": "https://www.youtube.com/@a16z", "title": "YouTube: a16z"},
                {"platform": "web", "identifier": "a16z.com", "url": "https://a16z.com", "title": "Web: a16z"}
            ],
            "predictions": [
                {"event_hypothesis": "Венчурные инвестиции в ИИ-агентов и оборонные технологии обновят исторический рекорд", "speaker_confidence": 0.86, "domain": "tech"}
            ]
        },
        {
            "name": "Chamath Palihapitiya",
            "domain": "tech",
            "channel": "Social Capital & All-In Podcast",
            "bio": "Основатель и CEO венчурного фонда Social Capital, соведущий популярного подкаста All-In",
            "quote": "Энергетическая инфраструктура и атомная генерация станут главным узким местом и одновременно лучшей инвестицией эпохи ИИ.",
            "socials": [
                {"platform": "x", "identifier": "@chamath", "url": "https://x.com/chamath", "title": "X: @chamath"},
                {"platform": "youtube", "identifier": "All-In Podcast", "url": "https://www.youtube.com/@allin", "title": "YouTube: All-In Podcast"},
                {"platform": "web", "identifier": "socialcapital.com", "url": "https://www.socialcapital.com", "title": "Web: Social Capital"}
            ],
            "predictions": [
                {"event_hypothesis": "Крупнейшие тех-корпорации заключат прямые контракты на строительство малых модульных АЭС для дата-центров", "speaker_confidence": 0.84, "domain": "tech"}
            ]
        },
        {
            "name": "David Sacks",
            "domain": "tech",
            "channel": "Craft Ventures & All-In Podcast",
            "bio": "Сооснователь венчурного фонда Craft Ventures, экс-COO PayPal, эксперт по SaaS, ИИ и технополитике",
            "quote": "Дерегулирование инновационных отраслей — ИИ и цифровых активов — обеспечит сохранение технологического лидерства и приток капитала.",
            "socials": [
                {"platform": "x", "identifier": "@DavidSacks", "url": "https://x.com/DavidSacks", "title": "X: @DavidSacks"},
                {"platform": "youtube", "identifier": "All-In Podcast", "url": "https://www.youtube.com/@allin", "title": "YouTube: All-In"},
                {"platform": "web", "identifier": "craftventures.com", "url": "https://www.craftventures.com", "title": "Web: Craft Ventures"}
            ],
            "predictions": [
                {"event_hypothesis": "Корпоративный сектор перейдет от классических SaaS-подписок к оплате за результат работы ИИ-агентов", "speaker_confidence": 0.83, "domain": "tech"}
            ]
        },
        {
            "name": "Naval Ravikant",
            "domain": "tech",
            "channel": "AngelList",
            "bio": "Сооснователь AngelList, ранний венчурный инвестор в Uber, Twitter и крипто-инфраструктуру",
            "quote": "Код и медиа — это рычаги, не требующие разрешения, а криптография и ИИ умножают производительность индивидуальных создателей в сотни раз.",
            "socials": [
                {"platform": "x", "identifier": "@naval", "url": "https://x.com/naval", "title": "X: @naval"},
                {"platform": "youtube", "identifier": "Naval", "url": "https://www.youtube.com/@Navalism", "title": "YouTube: Naval"},
                {"platform": "web", "identifier": "nav.al", "url": "https://nav.al", "title": "Web: nav.al"}
            ],
            "predictions": [
                {"event_hypothesis": "Появятся первые компании с оценкой в $1 млрд и штатом менее 10 человек за счет полной ИИ-автоматизации", "speaker_confidence": 0.85, "domain": "tech"}
            ]
        },
        {
            "name": "Михаил Хазин",
            "domain": "macro",
            "channel": "Фонд Михаила Хазина",
            "bio": "Экономист, публицист, автор теории кризиса современной бреттон-вудской финансовой модели",
            "quote": "Разделение мировой экономики на валютные зоны усилит спрос на физическое золото и расчеты в национальных валютах.",
            "socials": [
                {"platform": "youtube", "identifier": "Михаил Хазин", "url": "https://www.youtube.com/results?search_query=Михаил+Хазин+экономика", "title": "YouTube: Михаил Хазин"},
                {"platform": "web", "identifier": "khazin.ru", "url": "https://khazin.ru", "title": "Web: khazin.ru"},
                {"platform": "x", "identifier": "Михаил Хазин", "url": "https://x.com/search?q=Михаил+Хазин", "title": "X: Упоминания"}
            ],
            "predictions": [
                {"event_hypothesis": "Доля расчетов в национальных валютах стран БРИКС превысит долю доллара во взаимной торговле", "speaker_confidence": 0.82, "domain": "macro"}
            ]
        },
        {
            "name": "Евгений Надоршин",
            "domain": "macro",
            "channel": "ПФ Капитал",
            "bio": "Главный экономист консалтинговой компании «ПФ Капитал», макроэкономический эксперт по рынку РФ и сырья",
            "quote": "Жесткая денежно-кредитная политика и высокая ключевая ставка сдерживают кредитный импульс, формируя предпосылки для будущего разворота.",
            "socials": [
                {"platform": "youtube", "identifier": "Евгений Надоршин", "url": "https://www.youtube.com/results?search_query=Евгений+Надоршин+прогноз", "title": "YouTube: Интервью"},
                {"platform": "web", "identifier": "РБК / Коммерсантъ", "url": "https://news.google.com/search?q=Евгений+Надоршин", "title": "Web: Публикации в СМИ"},
                {"platform": "x", "identifier": "Евгений Надоршин", "url": "https://x.com/search?q=Евгений+Надоршин", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "Замедление кредитования приведет к постепенному снижению инфляционного давления во втором полугодии", "speaker_confidence": 0.79, "domain": "macro"}
            ]
        },
        {
            "name": "Александр Лосев",
            "domain": "macro",
            "channel": "Спутник — Управление Капиталом",
            "bio": "Генеральный директорУК «Спутник — Управление Капиталом», эксперт по глобальным финансовым и сырьевым рынкам",
            "quote": "Геополитическая премия в сырьевых активах и растущее энергопотребление ЦОД поддержат цены на энергоносители и промышленные металлы.",
            "socials": [
                {"platform": "youtube", "identifier": "Александр Лосев", "url": "https://www.youtube.com/results?search_query=Александр+Лосев+экономика", "title": "YouTube: Выступления"},
                {"platform": "web", "identifier": "Финам / РБК", "url": "https://news.google.com/search?q=Александр+Лосев+Спутник", "title": "Web: Аналитика"},
                {"platform": "x", "identifier": "Александр Лосев", "url": "https://x.com/search?q=Александр+Лосев", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "Спрос со стороны энергетики и дата-центров приведет к росту цен на медь и уран", "speaker_confidence": 0.81, "domain": "macro"}
            ]
        },
        {
            "name": "Ярослав Кабаков",
            "domain": "macro",
            "channel": "Финам Инвестиции",
            "bio": "Директор по стратегии инвестиционной компании «Финам», аналитик фондового рынка",
            "quote": "Дивидендные истории и компании с низкой долговой нагрузкой покажут наилучшую устойчивость в период высоких процентных ставок.",
            "socials": [
                {"platform": "youtube", "identifier": "Финам Инвестиции", "url": "https://www.youtube.com/@finam_invest", "title": "YouTube: Финам"},
                {"platform": "web", "identifier": "finam.ru", "url": "https://www.finam.ru", "title": "Web: Финам"},
                {"platform": "x", "identifier": "Ярослав Кабаков", "url": "https://x.com/search?q=Ярослав+Кабаков", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "Акции экспортеров и компаний с чистой денежной позицией опередят широкий индекс", "speaker_confidence": 0.78, "domain": "macro"}
            ]
        },
        {
            "name": "Дмитрий Солодин",
            "domain": "macro",
            "channel": "Solodin Live",
            "bio": "Инвестиционный управляющий и портфельный аналитик рынков США, Азии и цифровых активов",
            "quote": "Сектор полупроводников и облачной ИИ-инфраструктуры сохраняет лидерство по темпам роста выручки, но требует селективного отбора по оценкам.",
            "socials": [
                {"platform": "youtube", "identifier": "Дмитрий Солодин", "url": "https://www.youtube.com/results?search_query=Дмитрий+Солодин", "title": "YouTube: Дмитрий Солодин"},
                {"platform": "web", "identifier": "finversia.ru", "url": "https://news.google.com/search?q=Дмитрий+Солодин+инвестиции", "title": "Web: Обзоры"},
                {"platform": "x", "identifier": "Дмитрий Солодин", "url": "https://x.com/search?q=Дмитрий+Солодин", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "Индекс технологического сектора NASDAQ продолжит обновлять максимумы за счет отчетов бигтеха", "speaker_confidence": 0.79, "domain": "tech"}
            ]
        },
        {
            "name": "Тимофей Мартынов",
            "domain": "macro",
            "channel": "Smart-Lab и Мозговитый",
            "bio": "Основатель крупнейшего в РФ сообщества трейдеров и инвесторов Smart-Lab.ru",
            "quote": "Фундаментальная оценка бизнеса по мультипликаторам EV/EBITDA и дивидендной доходности остается главным ориентиром для долгосрочного инвестора.",
            "socials": [
                {"platform": "youtube", "identifier": "Smart-Lab", "url": "https://www.youtube.com/@smartlabru", "title": "YouTube: Smart-Lab"},
                {"platform": "web", "identifier": "smart-lab.ru", "url": "https://smart-lab.ru", "title": "Web: Smart-Lab"},
                {"platform": "x", "identifier": "Smart-Lab", "url": "https://x.com/search?q=Smart-Lab", "title": "X: Поиск"}
            ],
            "predictions": [
                {"event_hypothesis": "При первых сигналах смягчения ДКП долговой рынок ОФЗ и акции голубых фишек покажут переоценку вверх", "speaker_confidence": 0.81, "domain": "macro"}
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
                if s.get("platform") != "telegram":
                    socials.append(dict(s))

        # Parse handle_or_channel if provided
        if handle_or_channel:
            hc = handle_or_channel.strip()
            if "youtube.com" in hc or "youtu.be" in hc:
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

        # Guarantee Web / Media mentions link
        if not any(s["platform"] == "web" for s in socials):
            socials.append({
                "platform": "web",
                "identifier": "Google News",
                "url": f"https://news.google.com/search?q={encoded_name}",
                "title": "Упоминания в СМИ"
            })

        return socials
