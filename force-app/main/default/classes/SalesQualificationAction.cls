public with sharing class SalesQualificationAction {
  public class Request {
    @InvocableVariable(label='Job Title')
    public String title;
    @InvocableVariable(label='Company Size')
    public String companySize;
    @InvocableVariable(label='Intent Notes')
    public String intent;
  }
  public class Result {
    @InvocableVariable(label='Score')
    public Integer score;
    @InvocableVariable(label='Tier')
    public String tier;
    @InvocableVariable(label='Next Step')
    public String nextStep;
  }
  @InvocableMethod(label='Score Sales Lead' description='Scores lead fit and suggests next step from title company size and intent')
  public static List<Result> scoreLeads(List<Request> items) {
    List<Result> out = new List<Result>();
    for (Request r : items) {
      String text = String.valueOf(r.title) + ' ' + String.valueOf(r.companySize) + ' ' + String.valueOf(r.intent);
      text = text.toLowerCase();
      Integer score = 40;
      if (text.contains('vp') || text.contains('director') || text.contains('cto') || text.contains('head')) score += 25;
      if (text.contains('enterprise') || text.contains('500')) score += 20;
      if (text.contains('demo') || text.contains('trial') || text.contains('pricing')) score += 15;
      if (score > 100) score = 100;
      Result res = new Result();
      res.score = score;
      if (score >= 75) {
        res.tier = 'Hot';
        res.nextStep = 'Book discovery call this week';
      } else if (score >= 55) {
        res.tier = 'Warm';
        res.nextStep = 'Send tailored demo clip and follow up';
      } else {
        res.tier = 'Nurture';
        res.nextStep = 'Add to nurture track';
      }
      out.add(res);
    }
    return out;
  }
}
