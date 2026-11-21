"""Pre-loaded scenario library. Line format:
name | love | work | money | inner | reversed | question the card asks the querent
Written in our own words from common tarot tradition; Veyra adapts it, never recites it."""

_RAW = """
The Fool | a new romance, or trusting again after a long pause | leaving the safe job, a first day somewhere new, a pivot into the unknown | a first leap into investing or self-employment with no safety net | the itch to start over; curiosity before fear | jumping without checking the ground; ignoring red flags; naive trust | What would you try if you knew you could not look foolish?
The Magician | a charming, focused partner; you deliberately creating the connection | skills finally lining up; pitching, launching, being the one with the plan | turning talent into income; using the tools already in hand | realizing you already hold everything needed; will turned into action | smooth talker with a hidden angle; scattered talent; a plan that is all show | What resources are you overlooking in your own hands?
The High Priestess | unspoken feelings, a partner who withholds, trusting a hunch about someone | quiet research, office politics beneath the surface, information not yet shared | hidden costs, something not fully disclosed; wait and observe | dreams, gut knowing, the pull to be still and listen | ignoring your gut; secrets leaking; someone performing wisdom they lack | What do you already know but have not admitted?
The Empress | pregnancy or deep nurturing love, a warm and sensual bond | creative projects that bloom, a caring workplace or boss | abundance, comfortable growth, spending on beauty and home | self-nurture, connection with body and nature | smothering care, creative drought, over-giving; dependency | Where do you need to be mothered, and where are you over-mothering?
The Emperor | a stable, protective, perhaps controlling partner; commitment with rules | authority, structure, promotion, a strong boss or the role of one | budgets, order, building long-term wealth through discipline | boundaries, taking charge of your own life | tyranny, rigid control, a father-figure conflict, chaos from no discipline | Where do you need structure, and where is your control choking something?
The Hierophant | marriage, family approval, shared values, traditional commitment | institutions, mentors, credentials, following the established route | conventional finance, banks, advisors, the safe standard path | a belief system, a teacher, asking what you were taught and still hold | rebelling against rules, an unorthodox path, stifling conformity | Which inherited rule are you following without having chosen it?
The Lovers | a real choice of heart, deep alignment, a love that asks honesty | a partnership or a fork between two paths that both appeal | a joint venture; choosing with values, not only numbers | integrating head and heart; choosing who you will be | misalignment, temptation, avoiding a decision, a relationship out of sync | Which choice would you make if it matched who you really are?
The Chariot | momentum in love, pushing through obstacles together | driving a career forward, ambition, a move or commute, winning through focus | pushing to a financial goal, buying a vehicle or big asset | steering opposing impulses with will | losing control, aggression, spinning wheels, no clear direction | What are the two forces pulling you, and who is holding the reins?
Strength | patient, compassionate love; calming a partner or being calmed | quiet leadership, handling a difficult person with grace | steady restraint rather than impulse spending | courage that is gentle; taming fear and anger | self-doubt, raw emotion spilling, burnout from suppressing | Where would gentleness succeed where force has failed?
The Hermit | solitude after a split, a slow, introspective love, distance for clarity | solo deep work, mentoring, stepping back to rethink a career | careful audit, living lean to find clarity | a retreat, a search for your own light | isolation turning to loneliness, hiding from help, lost direction | What answer would you hear if the noise stopped for a week?
Wheel of Fortune | a turning point, fated meeting or a cycle repeating | luck, a sudden opening or shift in the industry | windfall or reversal; cycles of boom and bust | accepting that life moves in cycles | bad timing, resisting change, repeating the same cycle | What cycle keeps repeating, and what is yours to change?
Justice | a fair resolution, honest accounting in a relationship, legal matters like divorce or custody | contracts, fair evaluation, accountability, legal or HR matters | settlements, taxes, fair pay, cause-and-effect with money | honest self-assessment; owning consequences | unfairness, dodging responsibility, bias, a delayed verdict | What truth have you not yet accounted for?
The Hanged Man | a pause in love, seeing a partner from a new angle, letting go | a stalled project, forced waiting, a sacrifice for a better view | holding off a decision, delayed returns | surrender, suspended animation before insight | stalling, martyrdom, sacrificing for nothing | What shifts if you looked at this upside down?
Death | the end of a relationship or phase, a deep transformation of a bond | a job ending, a field changing, a role you have outgrown | closing an old account or ending a financial era | grief followed by rebirth; shedding an identity | clinging to what is over, stagnation, fear of the ending | What is already over that you are still holding onto?
Temperance | a balanced, patient, healing relationship | blending teams or skills, steady moderation, a calm mediator | budgeting, measured saving and spending, pacing | integration, finding the middle path | excess, imbalance, impatience, rushing a blend | Where have you tipped too far, and what would balance feel like?
The Devil | obsession, toxic attachment, jealousy, chemistry that binds | golden handcuffs, a toxic workplace, workaholism | debt, addiction to spending, being owned by money | shadow, patterns you feel unable to leave | breaking free, naming the chain, early recovery from a hold | What do you tell yourself you cannot leave, and is the chain truly locked?
The Tower | a sudden breakup, shocking truth revealed, a foundation cracking | sudden layoff, a collapse of a structure, a revelation that forces change | a financial shock, a sudden bill, assets disrupted | an awakening that clears false foundations | narrowly avoided disaster, delaying the inevitable, fear of the crash | What was built on a lie, and what is already shaking?
The Star | healing after hurt, hope, a gentle renewal of love | recovery after a setback, inspiration, a long-term vision | slow rebuilding, modest hope, generosity | faith, calm after storm, being open and seen | despair, discouragement, hope run dry, fatigue | What small light can you still see ahead?
The Moon | uncertainty, mixed signals, a partner not fully knowable | confusing situation, unclear info, working in the dark | opaque finances, a deal that smells off, hold off signing | fear, dreams, anxiety, intuition mixed with projection | fog clearing, secrets surfacing, release of fear | Which fear is distorting what you see?
The Sun | joy, a warm open relationship, a happy child | success, recognition, clarity at work | prosperity, relief, good fortune | vitality, confidence, being truly seen | a dimmed joy, temporary sadness, over-optimism | What would feel like pure daylight for you right now?
Judgement | a second chance, reconciliation, a calling to be honest about the past | a vocational calling, a review, a major career decision | reckoning with finances, a fresh start after assessment | an inner summons, forgiveness, rising to your better self | self-judgment, ignoring the call, refusing to forgive | What is calling you to rise, and what keeps you from answering?
The World | commitment fulfilled, a bond that feels whole | completion of a big project, travel, graduation, finishing a cycle | financial stability or goal reached | integration, wholeness, the end of a chapter | unfinished business, a missing last step, delayed closure | What is one piece away from finished?
"""

_WANDS = """
Ace of Wands | a spark of attraction or renewed passion | a new idea, startup energy, a fresh opportunity | a promising new venture | creative fire, a surge of motivation | delays, fizzled spark, missed opening | What are you eager to begin?
Two of Wands | planning a future together, long-distance or weighing relocation | choosing a strategy, expansion choices, planning a move abroad | invest vs stay, a plan in progress | standing at the edge of the comfort zone | fear of the unknown, no plan, playing small | What does leaving your comfort zone cost and gain?
Three of Wands | a partner far away, waiting for a ship to come in | expansion, overseas clients, long-range plans coming back | returns from earlier investments, international income | foresight, patience watching the horizon | delays, obstacles in expansion, plans not materializing | What are you waiting to see arrive?
Four of Wands | engagement, wedding, housewarming, family celebration | team milestone, community, a stable launch | home purchase, a stable base | harmony, belonging, relief | tension at home, a canceled celebration, instability | What are you ready to celebrate?
Five of Wands | rivalry, bickering, jealousy among suitors | office competition, brainstorms that clash, many cooks | competing for scarce resources, a pricing war | inner conflict, voices arguing | avoiding conflict, finding agreement, petty tension easing | What argument is really about something else?
Six of Wands | public success of a couple, pride in a partner | promotion, recognition, winning the pitch | a deserved reward, rising status | confidence earned, the victory lap | pride before a fall, no recognition, fear of exposure | What victory have you not allowed yourself to feel?
Seven of Wands | defending a relationship from outside criticism | holding your position, defending a role from rivals | protecting income or territory | standing your ground when challenged | feeling overwhelmed, giving in, burnout from defense | What is worth defending, and what are you only defending out of habit?
Eight of Wands | fast-moving romance, texting flurries, quick reunions | rapid progress, deadlines, travel, swift emails | quick deals, fast transactions | momentum, ideas moving fast | delays, miscommunication, frustration, scattered energy | What is moving faster than you can handle?
Nine of Wands | guardedness after past hurt, a wall up in love | exhaustion near the finish, tired but nearly done | a thin reserve, protecting savings | resilience, battle fatigue, hypervigilance | paranoia, burnout, quitting at the last step | Where are you armoring against something that is not attacking?
Ten of Wands | one partner carrying the load, relationship strain | overwork, too many responsibilities, taking on others' tasks | burdened by obligations, no help | carrying too much; unwilling to ask for help | dropping the load, delegating, a collapse from overload | What can you put down today?
Page of Wands | an exciting new flirt, a young creative person | an eager intern, a creative idea in infancy, a pitch to try | small trial ventures, side hustles | enthusiasm, trying a new craft | ideas with no follow-through, a flaky newcomer | What are you curious enough to try badly?
Knight of Wands | a passionate, impulsive suitor or traveler, whirlwind fling | a fast-moving go-getter, quick pivots, relocation | spending on impulse, risky ventures | restless energy, craving adventure | haste, burning out, a love-bomber who leaves | Where are you rushing because you are afraid to stand still?
Queen of Wands | a magnetic, confident partner; owning your sensuality | leader with charisma, a thriving creative business | confident, generous money handling | warm self-confidence, being the main character | jealous, domineering, insecure, fishing for attention | Where are you dimming your own light?
King of Wands | a bold, visionary partner who leads | entrepreneur, founder, bold boss | big-picture investor, ventures with vision | leadership with heart, honor | impulsive tyrant, ruthless, overpromising | What vision are you willing to stand behind?
"""

_CUPS = """
Ace of Cups | new love, an emotional opening, pregnancy | a role that finally matches your heart | emotional spending, a gift | an overflowing heart, compassion beginning | blocked feelings, an offer not fully received | What feeling are you ready to receive?
Two of Cups | a mutual, committed partnership, a soulmate bond | an equal business partnership, a good collaboration | a joint venture based on trust | harmony, mutual recognition | imbalance, a bond breaking, miscommunication | Is the giving and receiving equal?
Three of Cups | friends, celebration, a joyful gathering, a love triangle at its edge | team bonding, networking events, friends in business | shared costs, party spending | community, joy with others | gossip, overindulgence, excluded from the circle | Who nourishes you, and who drains you?
Four of Cups | boredom in a relationship, a missed offer, withdrawing | disengagement, not seeing a new opening | ignoring a good deal, apathy about earnings | contemplation, numbness, a sulk | awakening, accepting the offered cup | What offer have you not looked at because you were sulking?
Five of Cups | grief after a breakup, regret, mourning what was lost | a failed project, mourning a lost job | financial losses, spilled money | looking at what spilled and not at what remains | forgiveness, healing, turning to the cups still standing | What remains standing that you have not yet turned around to see?
Six of Cups | an old flame, childhood sweetheart, nostalgia | working with old colleagues, a familiar role | inheritance, family money, gifts | memories, innocence, healing the inner child | living in the past, idealizing it, refusing to grow | What from the past is calling, and is it nourishment or avoidance?
Seven of Cups | too many romantic options, fantasies, illusions about a partner | too many paths, idealized dreams, scattered focus | get-rich-quick fantasies, unrealistic plans | wishful thinking, overwhelmed by choices | clarity, choosing one, a reality check | Which of these dreams do you actually want to build?
Eight of Cups | walking away from a love that no longer feeds you | leaving a job that looks fine but feels empty | letting go of a comfortable but unfulfilling income | seeking something deeper, a pilgrimage | staying out of fear, going back, avoiding the leave | What have you outgrown but not yet left?
Nine of Cups | contentment, a satisfied love, desire fulfilled | job satisfaction, recognition, a goal reached | comfort, luxury, enough | the wish granted, pleasure | smugness, unfulfilled even with plenty, excess | What would enough feel like?
Ten of Cups | a happy family, lasting emotional fulfillment | a workplace that feels like family | a home that is paid for in joy, shared prosperity | emotional completeness | family disharmony, an ideal that is a facade | What does a good life look like when you describe it without anyone else?
Page of Cups | a sweet message, a tender new crush, an emotional young person | creative inspiration, an offer from the heart | small gifts, a creative side income | gentle intuition, a dreamy idea | emotional immaturity, creative blocks, mixed messages | What is the tender message you keep ignoring?
Knight of Cups | a romantic proposal, a courting partner, following the heart | an inspiring offer, a creative pursuit, a charming pitch | spending on romance | idealism, a dreamy quest | a moody lover, unrealistic romance, a charmer who disappoints | Is it romance you want, or the feeling of being chosen?
Queen of Cups | an empathic, emotionally mature partner | counselor, healer, an intuitive leader | careful, caring money use | deep intuition, compassion with boundaries | codependency, emotional overwhelm, martyrdom | Who needs your compassion, and have you left any for yourself?
King of Cups | a calm, emotionally steady partner | a diplomatic leader, counselor, a calm boss | wise, steady money advice | emotional mastery under pressure | emotional manipulation, repression, volatility | Can you feel deeply without being ruled by it?
"""

_SWORDS = """
Ace of Swords | a clear conversation, a breakthrough truth, a decisive question | a sharp idea, a key insight, a decision made | a clear financial decision, legal clarity | mental clarity cutting through fog | confusion, harsh words, clouded judgment | What truth is ready to be said plainly?
Two of Swords | a stalemate, refusing to choose between two people, emotional shutdown | a blocked decision, can't pick between options | frozen funds, avoiding a money decision | blindfolded neutrality, avoiding feeling | forced choice, information overload, the blindfold coming off | What are you refusing to look at to keep the peace?
Three of Swords | heartbreak, betrayal, a painful truth about a partner | a painful dismissal, a harsh review | financial heartbreak, bad news on a ledger | grief spoken plainly | healing, releasing pain, grief easing | What pain is asking to be felt?
Four of Swords | a break in the relationship, space to recover | rest after burnout, sabbatical, medical leave | pause on spending, saving during recovery | much-needed rest, meditation | exhaustion, being forced to rest, restlessness | What would real rest look like?
Five of Swords | a toxic fight, winning but at a cost, betrayal | a backstabbing coworker, a hollow win | a dispute over assets, unfair advantage | pride, a bitter victory | reconciliation, regret, making amends | What is winning costing you?
Six of Swords | leaving a hard relationship, moving to calmer waters | transition to a better workplace, a relocation | moving money, a calmer financial phase | healing passage | stuck in the past, a difficult move, baggage | What would you leave behind to cross the water?
Seven of Swords | infidelity, secrecy, a partner not being fully honest | office deception, taking shortcuts, theft of ideas | fraud, hidden expenses, getting away with it | self-deception, strategy | coming clean, caught in a lie, conscience | Where are you being less than fully honest, with them or yourself?
Eight of Swords | feeling trapped in a relationship, victim thinking | stuck in a role, self-imposed limits | feeling financially boxed in | a mind-made prison | seeing the exit, the blindfold off, release | What is the bind made of, and is the door actually locked?
Nine of Swords | anxiety about a partner, nightmares, sleepless worry | work stress, imposter anxiety, dread | financial anxiety spiralling | worry in the dark | relief, getting help, facing the fear in daylight | What do you worry about at 3 a.m., and who have you told?
Ten of Swords | a painful, final end of a relationship, betrayal | a total job loss, burnout collapse, rock bottom | financial ruin, hitting bottom | the end of a story | recovery, rising again, the worst is over | What does the sunrise at the end of this look like?
Page of Swords | a curious new person, a chatty flirt; gossip | an eager analyst, new ideas, vigilant new hire | a study of finances, researching a purchase | curiosity, a restless mind | spiteful gossip, hasty judgment, scattered thoughts | What question do you want to ask but have been afraid to?
Knight of Swords | a blunt, rushing partner; communication that charges ahead | an aggressive go-getter, rapid decisions | fast, careless trades | racing thoughts, ambition without a pause | recklessness, harsh words, burning bridges | What are you charging toward without thinking about the cost?
Queen of Swords | a partner with clear boundaries and a sharp mind | an objective, firm professional; a straight-talker | lean, clear-eyed budgeting | clarity with a scar behind it | bitterness, cold distance, cutting words | What boundary are you willing to hold with honesty?
King of Swords | a rational, principled partner who may lack warmth | a judge, lawyer, expert, strict executive | strategic planning, legal and financial authority | intellect used with ethics | cruelty, a manipulative authority, cold abuse of power | Can you be fair and kind at once?
"""

_PENTACLES = """
Ace of Pentacles | a stable, tangible new relationship, a home together | a solid opportunity: a job offer, a new business | a windfall, a seed of wealth | a grounded start | a missed opportunity, poor planning | What opportunity could you actually hold in your hands?
Two of Pentacles | juggling time between partner and life | multitasking, balancing jobs | cash flow juggling, balancing bills | adaptability | overwhelmed, dropped balls | What can you stop juggling?
Three of Pentacles | building a life together as a team | collaboration, apprenticeship, expert feedback | paid craft, a project with a team | pride in craft | lack of teamwork, poor-quality work, ignored input | Who could make this better by being in the room?
Four of Pentacles | possessive, guarded love; holding on tight | job security obsession, protecting resources | frugality, hoarding, stingy | the grip of security | letting go, spending freely, generosity or reckless loosening | What are you gripping, and what is it protecting you from?
Five of Pentacles | feeling left out, relationship hardship | job loss, unemployment, hardship | poverty, financial struggle, the snowy night | feeling cut off; unable to ask | recovery, help arriving, improving finances | What help is nearby that you have not knocked on?
Six of Pentacles | giving and receiving in balance, generosity | a raise, a fair bonus, mentorship | charity, loans, paying debts, a fair deal | generosity with boundaries | strings attached, debt dynamics, unequal giving | Is the giving in this situation fair and free?
Seven of Pentacles | slow-growing love that takes patience | a long project, waiting for results, assessing work | investments that ripen; patience with returns | assessing the harvest | impatience, wasted effort, poor returns | Is the effort rewarding you, or is it time to change fields?
Eight of Pentacles | working at the relationship, learning together | apprenticeship, skill mastery, studying hard | steady earning through craft | devotion to improvement | perfectionism, dull routine, shoddy work | What skill would pay off if you gave it another year?
Nine of Pentacles | independent love, a self-sufficient partner | financial independence, a thriving solo career | comfort, luxury, a paid-off home | self-reliance, refined solitude | overspending, an image of wealth, loneliness in luxury | What have you earned and not yet allowed yourself to enjoy?
Ten of Pentacles | a long-term family bond, marriage rooted in legacy | a family business, long-term career, established | inheritance, generational wealth, property | roots, belonging | family disputes over money, a fragile legacy | What legacy are you building, and is it yours to build?
Page of Pentacles | a slow, dependable new person | a student, a scholarship, a new job offer to study | a starter fund, a small investment | patient practical curiosity | procrastination, unrealistic plans, lack of progress | What practical first step can be taken this week?
Knight of Pentacles | a loyal, steady, if slow-moving partner | a reliable worker, routine, long-term plan | careful, steady saving | consistency, dependable effort | boredom, stuck routine, obsessive perfectionism | Is your steadiness serving you, or have you become stuck?
Queen of Pentacles | a nurturing, grounded partner; a loving home | a capable manager, a business that feels like a home | practical, generous, prosperous homemaker | being grounded and nurturing | work-home imbalance, smothering, material anxiety | How do you take care of yourself while taking care of others?
King of Pentacles | a stable, generous, protective partner | a successful business owner, a financial authority | wealth, assets, property | earned mastery | greed, stubborn, workaholism, poor business decisions | What does real security mean to you beyond money?
"""


def _parse():
    out = {}
    for block in (_RAW, _WANDS, _CUPS, _SWORDS, _PENTACLES):
        for ln in block.strip().splitlines():
            p = [x.strip() for x in ln.split("|")]
            if len(p) == 7:
                out[p[0]] = dict(zip(("love", "work", "money", "inner", "rev", "ask"), p[1:]))
    # minors listed by rank only in blocks above already carry full names
    return out


LORE = _parse()


# ---- guidance: what each card advises, where it tends to lead, and its yes/no lean ----------
# Line format: name | advice | outcome | yes/no (Yes, No or Maybe)
_GUIDE = """
The Fool | take the first small step before you feel ready | a fresh start that rewards curiosity | Yes
The Magician | use what is already in your hands and say clearly what you want | you make it happen through focused action | Yes
The High Priestess | wait, watch, and trust what you sense before you act | the truth surfaces quietly and your instinct proves right | Maybe
The Empress | nurture it and let it grow at its own pace | growth, comfort, something that blooms | Yes
The Emperor | set the rules, build the structure, take charge | stability you build and keep | Yes
The Hierophant | seek good counsel and the proven path | a recognized, traditional resolution or commitment | Yes
The Lovers | choose with your values, not only your wants | alignment and a union that asks for honesty | Yes
The Chariot | commit to one direction and drive through | victory through willpower | Yes
Strength | meet it with patience and gentle courage | you master it quietly, without force | Yes
The Hermit | step back and find your own answer in the quiet | clarity found alone; wisdom over speed | Maybe
Wheel of Fortune | ride the change instead of fighting it | a turning point; your luck shifts | Yes
Justice | be honest, weigh it fairly, accept the consequences | a fair result that matches what was put in | Maybe
The Hanged Man | pause, let go of control, look from a new angle | a delay that brings a breakthrough in perspective | Maybe
Death | let the ending happen so the new can begin | a clean transformation; one chapter closes for good | No
Temperance | find the middle path and go slowly | balance restored; a blend that finally works | Yes
The Devil | name what binds you and loosen its grip | you face the pattern that has hold of you | No
The Tower | let the false structure fall instead of propping it up | sudden change that clears the ground | No
The Star | keep faith and let yourself heal | hope renewed and a steady recovery | Yes
The Moon | do not act on fear; get more facts first | uncertainty lingers until the fog lifts | Maybe
The Sun | be open, be seen, enjoy it | success and joy in plain daylight | Yes
Judgement | answer the call and forgive what needs forgiving | a reckoning that frees you; a second chance | Yes
The World | finish what you started and celebrate it | completion and wholeness | Yes
Ace of Wands | act on the spark now while it is hot | a new venture or passion takes off | Yes
Two of Wands | make the plan and choose your direction | a bold decision opens a wider world | Yes
Three of Wands | look further ahead and prepare for growth | expansion; what you sent out comes back | Yes
Four of Wands | celebrate and honor what has been built | a happy milestone and a sense of home | Yes
Five of Wands | treat the conflict as healthy competition, not war | struggle that sharpens you | Maybe
Six of Wands | step forward and accept the recognition | public success and victory | Yes
Seven of Wands | hold your ground and defend what matters | you keep your position under challenge | Yes
Eight of Wands | move fast and answer quickly | rapid progress and news arriving | Yes
Nine of Wands | keep going; you are nearly there | you endure and finish strong | Maybe
Ten of Wands | put something down and ask for help | a heavy load that has to be lightened | No
Page of Wands | explore it playfully, like a beginner | exciting news or a new spark | Yes
Knight of Wands | act boldly but do not burn out | fast, adventurous change | Yes
Queen of Wands | own your confidence and your warmth | you lead with charisma and win hearts | Yes
King of Wands | lead with vision and take the first step | you become the one others follow | Yes
Ace of Cups | open your heart and let the feeling in | new love or a new emotional beginning | Yes
Two of Cups | meet the other person halfway | a mutual, balanced connection | Yes
Three of Cups | lean on friends and celebrate together | joy shared with your people | Yes
Four of Cups | look up and notice what is being offered | an offer you can still choose to see | No
Five of Cups | grieve, then turn toward what remains | loss acknowledged, and what is left still stands | No
Six of Cups | draw on the sweetness of the past without living there | a reunion or a return to innocence | Yes
Seven of Cups | pick one dream and test it against reality | choices clarify once fantasy is set aside | Maybe
Eight of Cups | walk away from what no longer feeds you | leaving for something deeper | No
Nine of Cups | let yourself enjoy what you wished for | a wish fulfilled; contentment | Yes
Ten of Cups | invest in the people who feel like home | lasting happiness and harmony | Yes
Page of Cups | listen to the soft message or the creative nudge | a sweet surprise or tender news | Yes
Knight of Cups | follow your heart, but check that it is real | an offer or a romance arrives | Yes
Queen of Cups | lead with compassion and keep your boundaries | emotional security and deep understanding | Yes
King of Cups | stay calm and steady when feelings run high | balance and wise emotional control | Yes
Ace of Swords | say the true thing plainly | a breakthrough of clarity | Yes
Two of Swords | take off the blindfold and decide | a stalemate that lasts until you choose | Maybe
Three of Swords | let yourself feel the hurt so it can heal | a painful truth, then release | No
Four of Swords | rest before you act again | recovery and a needed pause | Maybe
Five of Swords | ask whether winning is worth the cost | a hollow victory, or a fight best walked away from | No
Six of Swords | move toward calmer waters | a transition that brings relief | Yes
Seven of Swords | be strategic, but stay honest | something hidden comes into play | No
Eight of Swords | notice the exit; the bindings are looser than they feel | freedom once you see your own power | No
Nine of Swords | say the worry out loud to someone you trust | the fear proves worse than the reality | No
Ten of Swords | accept the ending; the only way now is up | a painful end that clears the way for recovery | No
Page of Swords | ask questions and stay alert | news or information that sharpens your view | Maybe
Knight of Swords | act decisively, but think before you charge | swift change driven by ambition | Yes
Queen of Swords | set clear boundaries and speak directly | clarity and independence | Yes
King of Swords | decide with logic and fairness | a rational, principled resolution | Yes
Ace of Pentacles | plant the seed; take the practical opportunity | a solid new opportunity in the real world | Yes
Two of Pentacles | prioritize and keep the balls in the air | you manage the juggle and adapt | Maybe
Three of Pentacles | collaborate and value good craft | recognition for skilled teamwork | Yes
Four of Pentacles | protect what matters, but do not grip too tight | security kept, at the cost of flow | Maybe
Five of Pentacles | ask for help; it is closer than you think | hardship that eases once you reach out | No
Six of Pentacles | give and receive fairly | a fair exchange; support arriving | Yes
Seven of Pentacles | be patient and assess your investment | slow, steady growth that pays off | Maybe
Eight of Pentacles | keep practicing and put in the work | mastery through dedication | Yes
Nine of Pentacles | enjoy the independence you have earned | comfort and self-sufficiency | Yes
Ten of Pentacles | think long-term and build what lasts | lasting security and legacy | Yes
Page of Pentacles | take the first practical step and study | a new practical opportunity or offer | Yes
Knight of Pentacles | stay steady and keep doing the work | slow but reliable progress | Yes
Queen of Pentacles | care for yourself as well as others | comfort, security, a nurturing home | Yes
King of Pentacles | lead with practical wisdom and generosity | material success and stability | Yes
"""

# Tone of each card for mood direction: light lifts the room, heavy darkens it.
LIGHT = {"The Sun", "The Star", "The World", "The Empress", "Strength", "Temperance", "Judgement",
         "Ace of Cups", "Two of Cups", "Three of Cups", "Nine of Cups", "Ten of Cups", "Ace of Wands",
         "Four of Wands", "Six of Wands", "Ace of Pentacles", "Nine of Pentacles", "Ten of Pentacles",
         "Six of Pentacles", "Ace of Swords", "Six of Swords", "The Lovers", "The Magician"}
HEAVY = {"The Tower", "Death", "The Devil", "The Moon", "Three of Swords", "Nine of Swords",
         "Ten of Swords", "Eight of Swords", "Five of Swords", "Five of Cups", "Five of Pentacles",
         "Ten of Wands", "Seven of Swords", "Four of Cups", "Eight of Cups", "The Hanged Man"}

for _ln in _GUIDE.strip().splitlines():
    _p = [x.strip() for x in _ln.split("|")]
    if len(_p) == 4 and _p[0] in LORE:
        LORE[_p[0]].update(advice=_p[1], outcome=_p[2], yn=_p[3])
