public with sharing class ServiceTriageAction {
  public class Request {
    @InvocableVariable(required=true label='Case Subject')
    public String subject;
    @InvocableVariable(label='Case Description')
    public String details;
  }
  public class Result {
    @InvocableVariable(label='Priority')
    public String priority;
    @InvocableVariable(label='Suggested Queue')
    public String queue;
    @InvocableVariable(label='Reason')
    public String reason;
  }
  @InvocableMethod(label='Triage Service Case' description='Scores priority and suggests a queue from subject and details')
  public static List<Result> triage(List<Request> items) {
    List<Result> out = new List<Result>();
    for (Request r : items) {
      String text = String.valueOf(r.subject) + ' ' + String.valueOf(r.details);
      text = text.toLowerCase();
      Result res = new Result();
      if (text.contains('outage') || text.contains('down') || text.contains('urgent')) {
        res.priority = 'High';
        res.queue = 'Critical_Response';
        res.reason = 'Keyword match for outage or urgent language';
      } else if (text.contains('billing') || text.contains('refund')) {
        res.priority = 'Medium';
        res.queue = 'Billing';
        res.reason = 'Billing related request';
      } else {
        res.priority = 'Low';
        res.queue = 'General_Support';
        res.reason = 'Default triage bucket';
      }
      out.add(res);
    }
    return out;
  }
}
