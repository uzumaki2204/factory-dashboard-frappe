using System.Reflection;
using System.Text.Json;
using FactoryManagement.Infrastructure.Services;
using FactoryManagement.Domain.Entities;

// Executes the actual .NET methods, rather than reimplementing their formulas.
var payload = typeof(DashboardProductivityPayloadService);
object Call(string name, params object[] args) => payload.GetMethod(name, BindingFlags.Static | BindingFlags.NonPublic)!.Invoke(null, args)!;
var day = new DateOnly(2026, 11, 17);
var targets = new List<object>();
foreach (var hours in new decimal[] { 0, 4, 8, 9.5m })
foreach (var moment in new[] { "2026-11-16T23:59:59", "2026-11-17T07:29:59", "2026-11-17T07:30:00", "2026-11-17T09:30:00", "2026-11-17T11:30:00", "2026-11-17T12:00:00", "2026-11-17T12:30:00", "2026-11-17T16:30:00", "2026-11-18T00:00:00" })
    targets.Add(new { day = day.ToString("yyyy-MM-dd"), now = moment, hours, target = 519, expected = Call("CalculateCurrentTargetQuantity", day, 519, hours, DateTime.Parse(moment)) });
var slots = new List<object>();
foreach (var workDay in new[] { day.AddDays(-1), day, day.AddDays(1) })
foreach (var moment in new[] { "07:29:59", "07:30:00", "09:29:59", "09:30:00", "23:59:59" })
foreach (var quantity in new[] { 0, 80 })
    slots.Add(new { day = workDay.ToString("yyyy-MM-dd"), now = $"2026-11-17T{moment}", quantity,
        visible = Call("ShouldDisplaySlot", workDay, "07:30", "09:30", quantity, DateTime.Parse($"2026-11-17T{moment}")),
        current = Call("IsCurrentSlot", workDay, "07:30", "09:30", DateTime.Parse($"2026-11-17T{moment}")) });
var lineId = Guid.Parse("00000000-0000-0000-0000-000000000001");
var oldId = Guid.Parse("00000000-0000-0000-0000-000000000010");
var newId = Guid.Parse("00000000-0000-0000-0000-000000000011");
var reports = new[] {
    new ProductivityReport { Id = oldId, LineId = lineId, CreatedAt = DateTime.Parse("2026-11-17T08:00:00"), UpdatedAt = DateTime.Parse("2026-11-17T09:00:00") },
    new ProductivityReport { Id = newId, LineId = lineId, CreatedAt = DateTime.Parse("2026-11-17T10:00:00"), UpdatedAt = DateTime.Parse("2026-11-17T11:00:00") }
};
var latest = (ProductivityReport)Call("SelectLatestReport", lineId, reports);
var planId = Guid.Parse("00000000-0000-0000-0000-000000000020");
var newerPlanId = Guid.Parse("00000000-0000-0000-0000-000000000021");
reports[1].ProductivityProductionPlanId = planId;
var plans = new[] {
    new ProductivityProductionPlan { Id = planId, LineId = lineId, LineStartDate = day.AddDays(-4), ShipmentDate = day.AddDays(5) },
    new ProductivityProductionPlan { Id = newerPlanId, LineId = lineId, LineStartDate = day.AddDays(-1), ShipmentDate = day.AddDays(6) }
};
var selectedPlan = (ProductivityProductionPlan)Call("SelectPlan", lineId, day, plans, reports[1]);
var rates = new[] { (0, 0), (1, 3), (1, 16), (270, 434), (5, 100), (8, 137) }
    .Select(x => new { numerator = x.Item1, denominator = x.Item2, percent = x.Item2 == 0 ? 0m : Math.Round(x.Item1 / (decimal)x.Item2, 4, MidpointRounding.AwayFromZero) * 100 }).ToArray();
Console.WriteLine(JsonSerializer.Serialize(new { targets, slots, latest_report = latest.Id, selected_plan = selectedPlan.Id, rates }, new JsonSerializerOptions { WriteIndented = true }));
