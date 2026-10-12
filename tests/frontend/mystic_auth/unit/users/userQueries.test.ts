import { beforeEach, describe, expect, it } from "vitest";
import MockAdapter from "axios-mock-adapter";

import api from "@/api/axiosInstance";
import { fetchAllMatchingUserEmails, SELECT_ALL_MATCHING_MAX } from "@/users/queries/userQueries";

const mock = new MockAdapter(api);

beforeEach(() => mock.reset());

describe("fetchAllMatchingUserEmails", () => {
    it("collects all pages until the server total is reached", async () => {
        const requests: number[] = [];
        mock.onGet("/users/").reply((config) => {
            const offset = Number(config.params?.offset);
            requests.push(offset);
            if (offset === 0) {
                return [200, [{ email: "first@example.com" }], { "x-total-count": "2" }];
            }
            return [200, [{ email: "second@example.com" }], { "x-total-count": "2" }];
        });

        await expect(fetchAllMatchingUserEmails({ search: "example" })).resolves.toEqual([
            "first@example.com",
            "second@example.com",
        ]);
        expect(requests).toEqual([0, 1000]);
    });

    it("stops safely when a proxy omits the total header", async () => {
        mock.onGet("/users/").reply(200, [{ email: "one@example.com" }]);

        await expect(fetchAllMatchingUserEmails({ search: "one" })).resolves.toEqual(["one@example.com"]);
    });

    it("stops when the API returns an empty page even with a stale total", async () => {
        mock.onGet("/users/").reply(200, [], { "x-total-count": "99" });

        await expect(fetchAllMatchingUserEmails({})).resolves.toEqual([]);
    });

    it("rejects before silently truncating a dangerously broad selection", async () => {
        const users = Array.from({ length: SELECT_ALL_MATCHING_MAX + 1 }, (_, i) => ({ email: `${i}@example.com` }));
        mock.onGet("/users/").reply(200, users, { "x-total-count": String(users.length) });

        await expect(fetchAllMatchingUserEmails({})).rejects.toThrow(/more than 2000 users/);
    });
});
