public with sharing class InternalHelpAction {
  public class Request {
    @InvocableVariable(label='Question')
    public String question;
    @InvocableVariable(label='Urgency')
    public String urgency;
  }
  public class Result {
    @InvocableVariable(label='Answer')
    public String answer;
    @InvocableVariable(label='Open Ticket')
    public Boolean openTicket;
    @InvocableVariable(label='Queue')
    public String queue;
  }
  @InvocableMethod(label='Answer IT Question' description='Drafts an IT answer and flags when a ticket is needed')
  public static List<Result> answerIt(List<Request> items) {
    List<Result> out = new List<Result>();
    for (Request r : items) {
      String text = String.valueOf(r.question) + ' ' + String.valueOf(r.urgency);
      text = text.toLowerCase();
      Result res = new Result();
      if (text.contains('vpn') || text.contains('password reset') || text.contains('wifi')) {
        res.answer = 'Try the self serve reset guide first, then reply if still blocked.';
        res.openTicket = false;
        res.queue = 'Self_Serve';
      } else if (text.contains('laptop') || text.contains('crash') || text.contains('urgent')) {
        res.answer = 'Likely needs hands on support. Opening a ticket with device details.';
        res.openTicket = true;
        res.queue = 'Desktop_Support';
      } else {
        res.answer = 'Logged for IT review with suggested priority.';
        res.openTicket = true;
        res.queue = 'General_IT';
      }
      out.add(res);
    }
    return out;
  }
}
