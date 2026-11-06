@IsTest
private class ServiceTriageActionTest {
  @IsTest
  static void highPriorityOnOutage() {
    ServiceTriageAction.Request r = new ServiceTriageAction.Request();
    r.subject = 'Store checkout down';
    r.details = 'Outage at checkout since morning';
    List<ServiceTriageAction.Result> res = ServiceTriageAction.triage(new List<ServiceTriageAction.Request>{ r });
    System.assertEquals(1, res.size());
    System.assertEquals('High', res[0].priority);
    System.assertEquals('Critical_Response', res[0].queue);
  }
  @IsTest
  static void bulkSafe() {
    List<ServiceTriageAction.Request> items = new List<ServiceTriageAction.Request>();
    for (Integer i = 0; i < 10; i++) {
      ServiceTriageAction.Request r = new ServiceTriageAction.Request();
      r.subject = 'Billing question ' + i;
      r.details = 'Refund status';
      items.add(r);
    }
    List<ServiceTriageAction.Result> res = ServiceTriageAction.triage(items);
    System.assertEquals(10, res.size());
  }
}
