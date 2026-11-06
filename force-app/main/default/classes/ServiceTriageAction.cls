/**
 * Service Triage recommendation engine.
 *
 * v1 contract: recommendation only. This class SUGGESTS a priority and a
 * queue for a support request. It never creates, updates, assigns, routes,
 * or escalates any record. Queue and priority values are labels for a
 * human or an agent conversation to act on. They are not validated
 * against queues in any org, and no org queue needs to exist.
 *
 * Outcomes: SUGGESTED means a confident suggestion is returned.
 * NEEDS_CLARIFICATION means input is missing or too thin to triage.
 * NEEDS_REVIEW means signals conflict, so a human should decide.
 * Priority and queue are set only when outcome is SUGGESTED.
 *
 * Input limits: subject is scored on its first 255 chars, details on
 * its first 4000 chars. Longer inputs set truncated to true and note
 * it in the reason. Output order always matches input order. A null
 * list returns an empty list. A null entry returns
 * NEEDS_CLARIFICATION at its index.
 *
 * Matching is deterministic, word based, and bulk safe. No queries,
 * no DML. Customer text is treated as data only. Override style
 * phrases never change the rules; beside a severity signal they
 * force NEEDS_REVIEW, and alone they are inert because v1 takes
 * no actions.
 *
 * Negation is scoped to the clause containing the signal. Clauses
 * split on comma, semicolon, colon, period, question, exclaim, and
 * the word but. A negation word only suppresses a signal in its
 * own clause within four words. Straight and curly apostrophes are
 * joined before matching, so isn't and isn’t both become isnt.
 * Billing signals respect negation the same way. The same severity
 * word affirmed in one clause and negated in another is treated as
 * a conflict and returns NEEDS_REVIEW. Uncertain phrasing with a
 * severity signal also returns NEEDS_REVIEW.
 */
public with sharing class ServiceTriageAction {
  public static final String OUTCOME_SUGGESTED = 'SUGGESTED';
  public static final String OUTCOME_CLARIFY = 'NEEDS_CLARIFICATION';
  public static final String OUTCOME_REVIEW = 'NEEDS_REVIEW';

  public static final Integer SUBJECT_MAX = 255;
  public static final Integer DETAILS_MAX = 4000;
  public static final Integer MIN_WORDS_FOR_DEFAULT = 4;
  public static final Integer NEGATION_WINDOW = 4;

  public static final String QUEUE_CRITICAL = 'Critical_Response';
  public static final String QUEUE_BILLING = 'Billing';
  public static final String QUEUE_GENERAL = 'General_Support';

  private static final Set<String> HIGH_WORDS = new Set<String>{
    'outage', 'outages', 'down', 'urgent', 'urgently', 'critical',
    'emergency', 'emergencies', 'sev0', 'sev1', 'breach', 'breached',
    'hacked', 'shutdown'
  };
  private static final List<String> HIGH_PHRASES = new List<String>{
    'system down', 'service down', 'data breach', 'security incident',
    'stopped working'
  };
  private static final Set<String> BILLING_WORDS = new Set<String>{
    'billing', 'billed', 'invoice', 'invoices', 'invoicing', 'refund',
    'refunds', 'refunded', 'charge', 'charged', 'charges', 'payment',
    'payments', 'overcharge', 'overcharged'
  };
  private static final Set<String> NEGATIONS = new Set<String>{
    'not', 'no', 'never', 'none', 'isnt', 'arent', 'wasnt', 'werent',
    'dont', 'doesnt', 'didnt', 'cant', 'cannot', 'couldnt', 'wont',
    'wouldnt', 'shouldnt', 'without', 'hardly', 'barely'
  };
  private static final List<String> CONFLICT_MARKERS = new List<String>{
    'false alarm', 'all clear', 'resolved', 'just testing', 'test only',
    'ignore previous', 'ignore all rules', 'disregard', 'override the rules'
  };
  private static final List<String> UNCERTAINTY_MARKERS = new List<String>{
    'maybe', 'might be', 'may be', 'possible', 'possibly', 'not sure',
    'unsure', 'uncertain', 'unclear', 'checking now', 'checking'
  };
  private static final List<String> MAINTENANCE_WORDS = new List<String>{
    'scheduled', 'planned maintenance', 'maintenance window'
  };
  private static final List<String> MOTION_GUARDS = new List<String>{
    'calm down', 'sit down', 'slow down', 'write down', 'lie down',
    'step down', 'break down', 'down the hall', 'down the street',
    'down the road'
  };

  public class Request {
    @InvocableVariable(required=true label='Case Subject')
    public String subject;
    @InvocableVariable(label='Case Description')
    public String details;
  }

  public class Result {
    @InvocableVariable(label='Outcome')
    public String outcome;
    @InvocableVariable(label='Priority')
    public String priority;
    @InvocableVariable(label='Suggested Queue')
    public String queue;
    @InvocableVariable(label='Reason')
    public String reason;
    @InvocableVariable(label='Input Truncated')
    public Boolean truncated;
  }

  @InvocableMethod(label='Triage Service Case' description='Suggests a priority and queue for a support request. Recommendation only; updates no records.')
  public static List<Result> triage(List<Request> items) {
    List<Result> out = new List<Result>();
    if (items == null) {
      return out;
    }
    for (Request r : items) {
      out.add(scoreOne(r));
    }
    return out;
  }

  private static Result scoreOne(Request r) {
    Result res = new Result();
    res.truncated = false;
    if (r == null) {
      res.outcome = OUTCOME_CLARIFY;
      res.reason = 'Empty request entry.';
      return res;
    }
    String subject = r.subject == null ? '' : r.subject;
    String details = r.details == null ? '' : r.details;
    if (String.isBlank(subject) && String.isBlank(details)) {
      res.outcome = OUTCOME_CLARIFY;
      res.reason = 'No subject or details provided. Ask what the issue is.';
      return res;
    }
    if (subject.length() > SUBJECT_MAX) {
      subject = subject.substring(0, SUBJECT_MAX);
      res.truncated = true;
    }
    if (details.length() > DETAILS_MAX) {
      details = details.substring(0, DETAILS_MAX);
      res.truncated = true;
    }
    String low = straightenApostrophes(subject + ' ' + details).toLowerCase();
    low = low.replace('\'', '');
    String text = normalizeSpaces(low);
    for (String guard : MOTION_GUARDS) {
      text = text.replace(guard, ' ');
    }
    text = squeeze(text);
    List<String> toks = tokensOf(text);
    List<String> clauses = clausesOf(low);
    List<String> highHits = new List<String>();
    List<String> negatedHigh = new List<String>();
    List<String> billHits = new List<String>();
    for (String clause : clauses) {
      List<String> ctoks = tokensOf(clause);
      collectHighForClause(ctoks, clause, highHits, negatedHigh);
      collectBillForClause(ctoks, billHits);
    }
    Boolean conflict = hasAny(text, CONFLICT_MARKERS);
    Boolean maintenance = hasAny(text, MAINTENANCE_WORDS);
    Boolean uncertain = hasAny(text, UNCERTAINTY_MARKERS);
    Boolean sameSignal = sameSignalConflict(highHits, negatedHigh);

    if (!highHits.isEmpty() && (conflict || maintenance || uncertain || sameSignal)) {
      res.outcome = OUTCOME_REVIEW;
      res.reason = 'Conflicting signals found: ' + joinFirst(highHits, 3) + '. Needs human review.' + truncNote(res.truncated);
      return res;
    }
    if (!highHits.isEmpty()) {
      res.outcome = OUTCOME_SUGGESTED;
      res.priority = 'High';
      res.queue = QUEUE_CRITICAL;
      res.reason = 'Severity signals found: ' + joinFirst(highHits, 3) + '. Suggested for urgent handling.' + truncNote(res.truncated);
      return res;
    }
    if (!billHits.isEmpty() && (conflict || maintenance)) {
      res.outcome = OUTCOME_REVIEW;
      res.reason = 'Conflicting signals found: ' + joinFirst(billHits, 3) + '. Needs human review.' + truncNote(res.truncated);
      return res;
    }
    if (!billHits.isEmpty()) {
      res.outcome = OUTCOME_SUGGESTED;
      res.priority = 'Medium';
      res.queue = QUEUE_BILLING;
      res.reason = 'Billing signals found: ' + joinFirst(billHits, 3) + '.' + truncNote(res.truncated);
      return res;
    }
    if (toks.size() < MIN_WORDS_FOR_DEFAULT) {
      res.outcome = OUTCOME_CLARIFY;
      res.reason = 'Too little detail to triage. Ask for the issue and its impact.' + truncNote(res.truncated);
      return res;
    }
    res.outcome = OUTCOME_SUGGESTED;
    res.priority = 'Low';
    res.queue = QUEUE_GENERAL;
    res.reason = 'No severity signals found. Default general queue for human sorting.' + truncNote(res.truncated);
    return res;
  }

  private static void collectHighForClause(
    List<String> toks, String clauseText, List<String> affirmed, List<String> negated
  ) {
    for (Integer i = 0; i < toks.size(); i++) {
      if (HIGH_WORDS.contains(toks[i])) {
        if (negatedBefore(toks, i)) {
          negated.add(toks[i]);
        } else {
          affirmed.add(toks[i]);
        }
      }
    }
    for (String phrase : HIGH_PHRASES) {
      Integer atPos = clauseText.indexOf(phrase);
      if (atPos < 0) {
        continue;
      }
      Integer tokIdx = tokensOf(clauseText.substring(0, atPos)).size();
      if (negatedBefore(toks, tokIdx)) {
        negated.add(phrase);
      } else {
        affirmed.add(phrase);
      }
    }
  }

  private static void collectBillForClause(List<String> toks, List<String> affirmed) {
    for (Integer i = 0; i < toks.size(); i++) {
      if (BILLING_WORDS.contains(toks[i]) && !negatedBefore(toks, i)) {
        affirmed.add(toks[i]);
      }
    }
  }

  private static Boolean sameSignalConflict(List<String> affirmed, List<String> negated) {
    if (affirmed.isEmpty() || negated.isEmpty()) {
      return false;
    }
    Set<String> affWords = new Set<String>();
    for (String hit : affirmed) {
      for (String w : hit.split(' ')) {
        affWords.add(stemKey(w));
      }
    }
    for (String hit : negated) {
      for (String w : hit.split(' ')) {
        if (affWords.contains(stemKey(w))) {
          return true;
        }
      }
    }
    return false;
  }

  private static String stemKey(String word) {
    if (word != null && word.endsWith('s') && word.length() > 3) {
      return word.substring(0, word.length() - 1);
    }
    return word;
  }

  private static Boolean negatedBefore(List<String> toks, Integer idx) {
    Integer fromIdx = Math.max(0, idx - NEGATION_WINDOW);
    for (Integer i = fromIdx; i < idx && i < toks.size(); i++) {
      if (NEGATIONS.contains(toks[i])) {
        return true;
      }
    }
    return false;
  }

  private static Boolean hasAny(String text, List<String> needles) {
    for (String n : needles) {
      if (text.contains(n)) {
        return true;
      }
    }
    return false;
  }

  private static String straightenApostrophes(String raw) {
    String s = raw == null ? '' : raw;
    s = s.replace('\u2019', '\'');
    s = s.replace('\u2018', '\'');
    s = s.replace('`', '\'');
    s = s.replace('\u00B4', '\'');
    return s;
  }

  private static String normalizeSpaces(String raw) {
    String low = raw == null ? '' : raw;
    low = low.replaceAll('[^a-z0-9 ]', ' ');
    return squeeze(low);
  }

  private static List<String> clausesOf(String low) {
    List<String> clauses = new List<String>();
    if (String.isBlank(low)) {
      return clauses;
    }
    String marked = low.replace(' but ', '|');
    marked = marked.replaceAll('[,;:.!?]+', '|');
    for (String part : marked.split('\\|')) {
      String cleaned = normalizeSpaces(part);
      for (String guard : MOTION_GUARDS) {
        cleaned = cleaned.replace(guard, ' ');
      }
      cleaned = squeeze(cleaned);
      if (String.isNotBlank(cleaned)) {
        clauses.add(cleaned);
      }
    }
    return clauses;
  }

  private static String squeeze(String s) {
    return s.replaceAll(' +', ' ').trim();
  }

  private static List<String> tokensOf(String text) {
    List<String> toks = new List<String>();
    if (String.isBlank(text)) {
      return toks;
    }
    for (String t : text.split(' ')) {
      if (String.isNotBlank(t)) {
        toks.add(t);
      }
    }
    return toks;
  }

  private static String joinFirst(List<String> items, Integer limitCount) {
    List<String> head = new List<String>();
    for (Integer i = 0; i < items.size() && i < limitCount; i++) {
      head.add(items[i]);
    }
    return String.join(head, ', ');
  }

  private static String truncNote(Boolean wasTruncated) {
    return wasTruncated ? ' Input exceeded scoring limits and was truncated.' : '';
  }
}
