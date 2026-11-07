import { useQuery } from "@tanstack/react-query";
import { Bell, CalendarDays, Coins, Contact, ExternalLink, MessageCircle, UserRound } from "lucide-react";
import { Link } from "react-router-dom";
import { PageHeader } from "../components/ui";
import { accountContentService } from "../services/chapelflow";
import { useAuth } from "./auth-context";

function accountLabel(community: "staff" | "guest" | "student" | undefined) {
  return community === "staff" ? "Staff" : "Guest";
}

export function MemberAccountHomePage() {
  const { user } = useAuth();
  const announcements = useQuery({
    queryKey: ["account-announcements"],
    queryFn: async () => (await accountContentService.announcements()).data,
  });
  const label = accountLabel(user?.community);
  const firstName = user?.name.split(/\s+/)[0] || label.toLowerCase();

  return (
    <div className="account-home">
      <PageHeader
        eyebrow={`${label} account`}
        title={`Welcome, ${firstName}.`}
        description="Your account keeps chapel information and support within easy reach. Attendance and student communities are not part of this account."
      />
      <section className="account-home__welcome">
        <div>
          <p className="eyebrow">Chrisland University Chapel</p>
          <h2>Stay informed. Keep your account secure.</h2>
          <p>Use this space for chapel-wide updates, public services, and direct support from the chapel office.</p>
        </div>
        <Link className="button button--primary" to="/contact">
          <Contact /> Contact the chapel
        </Link>
      </section>
      <div className="account-home__grid">
        <section className="panel account-home__card account-home__card--upper-room">
          <MessageCircle />
          <div><p className="eyebrow">Community space</p><h2>The Upper Room</h2><p>Share an encouraging thought or a chapel moment with your community.</p><div className="account-home__links"><Link to="/app/upper-room">Open The Upper Room <ExternalLink /></Link></div></div>
        </section>
        <section className="panel account-home__card account-home__card--giving">
          <Coins />
          <div>
            <p className="eyebrow">Personal giving</p>
            <h2>Offerings and tithes</h2>
            <p>Give a personal offering or tithe through the chapel's secure Paystack checkout.</p>
            <div className="account-home__links"><Link to="/app/giving">Give securely <ExternalLink /></Link></div>
          </div>
        </section>
        <section className="panel account-home__card">
          <CalendarDays />
          <div>
            <p className="eyebrow">Plan a visit</p>
            <h2>Services and public events</h2>
            <p>See service times, chapel events, and programme information open to the wider university community.</p>
            <div className="account-home__links">
              <Link to="/service-times">Service times <ExternalLink /></Link>
              <Link to="/events">Upcoming events <ExternalLink /></Link>
            </div>
          </div>
        </section>
        <section className="panel account-home__card">
          <Bell />
          <div>
            <p className="eyebrow">From the chapel</p>
            <h2>Chapel-wide announcements</h2>
            {announcements.isPending ? <p>Loading published chapel updates…</p> : announcements.isError ? <p>Announcements are temporarily unavailable. Please try again shortly.</p> : announcements.data?.length ? <div className="account-home__announcements">{announcements.data.slice(0, 3).map((item) => <article key={item.id}><strong>{item.title}</strong><p>{item.body}</p></article>)}</div> : <p>No chapel-wide announcements have been published yet.</p>}
          </div>
        </section>
      </div>
      <section className="panel account-home__security">
        <UserRound />
        <div>
          <h2>Profile and security</h2>
          <p>Keep your email, phone number, and emergency contact details current. Your login remains private to you.</p>
        </div>
        <Link className="button button--secondary" to="/app/profile/edit">Manage profile</Link>
      </section>
    </div>
  );
}
